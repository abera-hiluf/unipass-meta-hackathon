from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from pathlib import PurePosixPath
import secrets
from typing import Protocol
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.document_validation import validate_document_content
from app.services.storage import PrivateObjectStorage, StorageError


LIVENESS_STEPS = ("blink", "turn_left", "turn_right")
_VIDEO_RULES = {".webm": "video/webm", ".mp4": "video/mp4", ".mov": "video/quicktime"}


@dataclass(frozen=True)
class LivenessAssessment:
    status: str
    reason_code: str
    provider: str


class LivenessAdapter(Protocol):
    def assess(self, content: bytes, content_type: str, steps: list[str]) -> LivenessAssessment: ...


class UnavailableLivenessAdapter:
    """Safe default: no biometric engine is installed or invoked."""

    def assess(self, content: bytes, content_type: str, steps: list[str]) -> LivenessAssessment:
        return LivenessAssessment("REVIEW_REQUIRED", "liveness_provider_not_configured", "unavailable")


class MockLivenessAdapter:
    def __init__(self, assessment: LivenessAssessment | None = None) -> None:
        self.assessment = assessment or LivenessAssessment("REVIEW_REQUIRED", "synthetic_uncertain", "mock")

    def assess(self, content: bytes, content_type: str, steps: list[str]) -> LivenessAssessment:
        return self.assessment


def get_liveness_adapter() -> LivenessAdapter:
    return UnavailableLivenessAdapter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_challenge(challenge_id: str) -> str:
    return hashlib.sha256(challenge_id.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def validate_liveness_challenge(verification: IdentityVerification, challenge_id: str, now: datetime | None = None) -> None:
    current_time = now or _now()
    if verification.liveness_status != "CHALLENGE_ISSUED" or not verification.liveness_challenge_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active liveness challenge exists")
    if verification.liveness_challenge_expires_at and _aware(verification.liveness_challenge_expires_at) <= current_time:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Liveness challenge has expired")
    if not hmac.compare_digest(verification.liveness_challenge_hash, _hash_challenge(challenge_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liveness challenge is invalid")


def validate_liveness_consent(consent: bool, capture_state: str) -> None:
    if not consent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Explicit liveness consent is required")
    if capture_state.strip().lower() != "completed_challenge":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A completed liveness challenge is required")


def issue_liveness_challenge(db: Session, user: User, verification_id: uuid.UUID) -> dict:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    if verification.status in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Verification is not accepting liveness")

    now = _now()
    if verification.liveness_challenge_expires_at and _aware(verification.liveness_challenge_expires_at) > now and not verification.liveness_challenge_used_at:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="An active liveness challenge already exists")

    challenge_id = secrets.token_urlsafe(32)
    steps = secrets.SystemRandom().sample(list(LIVENESS_STEPS), k=len(LIVENESS_STEPS))
    expires_at = now + timedelta(seconds=settings.liveness_challenge_ttl_seconds)
    if verification.liveness_status is None:
        verification.liveness_status = "NOT_STARTED"
    verification.transition_liveness_to("CHALLENGE_ISSUED")
    verification.liveness_challenge_hash = _hash_challenge(challenge_id)
    verification.liveness_challenge_steps = ",".join(steps)
    verification.liveness_challenge_issued_at = now
    verification.liveness_challenge_expires_at = expires_at
    verification.liveness_challenge_used_at = None
    verification.liveness_reason_code = None
    verification.liveness_provider = None
    db.commit()
    return {
        "verification_id": verification.id,
        "challenge_id": challenge_id,
        "steps": steps,
        "expires_at": expires_at,
        "liveness_status": verification.liveness_status,
    }


async def submit_liveness_capture(
    db: Session,
    user: User,
    verification_id: uuid.UUID,
    challenge_id: str,
    consent: bool,
    capture_state: str,
    upload: UploadFile,
    storage: PrivateObjectStorage,
    adapter: LivenessAdapter,
) -> IdentityVerification:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    validate_liveness_consent(consent, capture_state)
    validate_liveness_challenge(verification, challenge_id)

    extension = PurePosixPath(upload.filename or "").suffix.lower()
    expected_mime = _VIDEO_RULES.get(extension)
    is_image = extension in {".jpg", ".jpeg", ".png"}
    if expected_mime is None and not is_image:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported liveness capture format")
    if upload.content_type != expected_mime and not (is_image and upload.content_type in {"image/jpeg", "image/png"}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported liveness capture format")

    content = bytearray()
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.liveness_max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Liveness capture is too large")
    raw_content = bytes(content)
    if not raw_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liveness capture is empty")
    if is_image:
        try:
            validate_document_content(raw_content, extension)
        except StorageError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liveness capture is unreadable") from None
    elif not ((extension == ".webm" and raw_content.startswith(b"\x1a\x45\xdf\xa3")) or (extension in {".mp4", ".mov"} and raw_content[4:8] == b"ftyp")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liveness capture content is invalid")

    now = _now()
    object_key = f"liveness/{uuid.uuid4().hex}{extension}"
    try:
        storage.put_object(object_key, raw_content, upload.content_type or "application/octet-stream")
    except StorageError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Liveness storage is unavailable") from None

    steps = (verification.liveness_challenge_steps or "").split(",")
    verification.transition_liveness_to("PROCESSING")
    verification.liveness_capture_storage_key = object_key
    verification.liveness_challenge_used_at = now
    verification.liveness_consent_at = now
    verification.liveness_started_at = now
    try:
        assessment = adapter.assess(raw_content, upload.content_type or "application/octet-stream", steps)
        if assessment.status not in {"LIVE", "SPOOF_SUSPECTED", "REVIEW_REQUIRED", "FAILED"}:
            raise ValueError("Unsupported liveness assessment")
        verification.transition_liveness_to(assessment.status)
        verification.liveness_reason_code = assessment.reason_code
        verification.liveness_provider = assessment.provider
        verification.liveness_completed_at = _now()
        db.commit()
        db.refresh(verification)
        return verification
    except (SQLAlchemyError, ValueError):
        db.rollback()
        try:
            storage.delete_object(object_key)
        except StorageError:
            pass
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Liveness assessment could not be recorded") from None
