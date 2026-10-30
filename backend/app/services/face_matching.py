from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Protocol
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.document_validation import validate_document_content
from app.services.storage import PrivateObjectStorage, StorageError


class FaceMatchingError(RuntimeError):
    """A safe, non-sensitive face-matching failure."""


@dataclass(frozen=True)
class FaceMatchAssessment:
    status: str
    reason_code: str
    provider: str
    similarity_score: float | None = None


class FaceMatchingAdapter(Protocol):
    def compare(self, portrait: bytes, selfie: bytes, portrait_extension: str, selfie_extension: str) -> FaceMatchAssessment: ...


class UnavailableFaceMatchingAdapter:
    """Safe default until a reviewed, licensed biometric provider is configured."""

    def compare(self, portrait: bytes, selfie: bytes, portrait_extension: str, selfie_extension: str) -> FaceMatchAssessment:
        return FaceMatchAssessment("REVIEW_REQUIRED", "face_matching_provider_not_configured", "unavailable")


class MockFaceMatchingAdapter:
    """Synthetic test adapter; never used by default application configuration."""

    def __init__(self, assessment: FaceMatchAssessment | None = None) -> None:
        self.assessment = assessment or FaceMatchAssessment("REVIEW_REQUIRED", "synthetic_uncertain", "mock")

    def compare(self, portrait: bytes, selfie: bytes, portrait_extension: str, selfie_extension: str) -> FaceMatchAssessment:
        return self.assessment


def get_face_matching_adapter() -> FaceMatchingAdapter:
    return UnavailableFaceMatchingAdapter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _response(verification: IdentityVerification) -> dict:
    return {
        "verification_id": verification.id,
        "status": verification.face_match_status,
        "reason_code": verification.face_match_reason_code,
        "provider": verification.face_match_provider,
        "completed_at": verification.face_match_completed_at,
    }


def _extension(key: str | None) -> str:
    extension = PurePosixPath(key or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png"}:
        raise FaceMatchingError("unsupported_face_image")
    return extension


def start_face_matching(
    db: Session,
    user: User,
    verification_id: uuid.UUID,
    storage: PrivateObjectStorage,
    adapter: FaceMatchingAdapter,
) -> dict:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    if verification.status in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Verification is not accepting face matching")
    if not verification.portrait_storage_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document portrait is not available")
    if verification.selfie_status != "SUBMITTED" or not verification.selfie_storage_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selfie is not available")
    if verification.face_match_status == "PROCESSING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Face matching is already processing")

    try:
        portrait_extension = _extension(verification.portrait_storage_key)
        selfie_extension = _extension(verification.selfie_storage_key)
        portrait = storage.get_object(verification.portrait_storage_key)
        selfie = storage.get_object(verification.selfie_storage_key)
        validate_document_content(portrait, portrait_extension)
        validate_document_content(selfie, selfie_extension)
    except (StorageError, FaceMatchingError):
        verification.face_match_reason_code = "face_image_unavailable_or_invalid"
        verification.face_match_provider = "local_validation"
        if verification.face_match_status is None:
            verification.face_match_status = "NOT_STARTED"
        verification.transition_face_match_to("PROCESSING")
        verification.transition_face_match_to("FAILED")
        db.commit()
        return _response(verification)

    started_at = _now()
    try:
        if verification.face_match_status is None:
            verification.face_match_status = "NOT_STARTED"
        verification.transition_face_match_to("PROCESSING")
        verification.face_match_started_at = started_at
        assessment = adapter.compare(portrait, selfie, portrait_extension, selfie_extension)
        target = assessment.status.upper()
        if target not in {"MATCH", "NO_MATCH", "REVIEW_REQUIRED", "FAILED"}:
            raise FaceMatchingError("unsupported_face_match_status")
        if assessment.similarity_score is not None and not 0 <= assessment.similarity_score <= 1:
            raise FaceMatchingError("invalid_similarity_score")
        if target == "MATCH" and (assessment.similarity_score is None or assessment.similarity_score < settings.face_match_threshold):
            target = "REVIEW_REQUIRED"
            reason_code = "similarity_below_configured_threshold"
        else:
            reason_code = assessment.reason_code
        verification.transition_face_match_to(target)
        verification.face_match_score = assessment.similarity_score
        verification.face_match_reason_code = reason_code
        verification.face_match_provider = assessment.provider
        verification.face_match_completed_at = _now()
        db.commit()
        db.refresh(verification)
        return _response(verification)
    except (FaceMatchingError, SQLAlchemyError, ValueError):
        db.rollback()
        verification = db.get(IdentityVerification, verification_id)
        if verification is not None:
            if verification.face_match_status is None:
                verification.face_match_status = "NOT_STARTED"
            if verification.face_match_status == "PROCESSING":
                verification.transition_face_match_to("FAILED")
            verification.face_match_reason_code = "face_matching_failed"
            verification.face_match_completed_at = _now()
            db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Face matching is unavailable") from None
