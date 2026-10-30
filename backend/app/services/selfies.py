from __future__ import annotations

from pathlib import PurePosixPath
from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.document_validation import validate_document_content
from app.services.storage import PrivateObjectStorage, StorageError


_SELFIE_RULES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_signature(content: bytes, extension: str) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    return content.startswith(b"\x89PNG\r\n\x1a\n")


async def submit_selfie(
    db: Session,
    user: User,
    verification_id: uuid.UUID,
    upload: UploadFile,
    consent: bool,
    capture_state: str,
    storage: PrivateObjectStorage,
) -> IdentityVerification:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    if verification.status in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Verification is not accepting a selfie")
    if not consent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Explicit selfie consent is required")
    if capture_state.strip().lower() != "captured":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A confirmed selfie capture is required")

    extension = PurePosixPath(upload.filename or "").suffix.lower()
    expected_mime = _SELFIE_RULES.get(extension)
    if expected_mime is None or upload.content_type != expected_mime:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported selfie format")

    content = bytearray()
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.selfie_max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Selfie is too large")
    raw_content = bytes(content)
    if not raw_content or not _valid_signature(raw_content, extension):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selfie content is invalid")
    try:
        validate_document_content(raw_content, extension)
    except StorageError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selfie image is unreadable") from None

    object_key = f"selfies/{uuid.uuid4().hex}{extension}"
    try:
        storage.put_object(object_key, raw_content, expected_mime)
    except StorageError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Selfie storage is unavailable") from None

    now = _now()
    verification.selfie_status = "SUBMITTED"
    verification.selfie_storage_key = object_key
    verification.selfie_consent_at = now
    verification.selfie_submitted_at = now
    verification.selfie_reason_code = "submitted_for_future_liveness_review"
    try:
        db.commit()
        db.refresh(verification)
        return verification
    except SQLAlchemyError:
        db.rollback()
        try:
            storage.delete_object(object_key)
        except StorageError:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Selfie submission could not be recorded",
        ) from None
