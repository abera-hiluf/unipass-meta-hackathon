from __future__ import annotations

from pathlib import PurePosixPath
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.storage import PrivateObjectStorage, StorageError


SUPPORTED_DOCUMENT_TYPES = {"passport", "national_id"}
MAX_DOCUMENT_TYPE_LENGTH = 32

_FILE_RULES = {
    ".pdf": {"mime": "application/pdf", "signature": lambda content: content.startswith(b"%PDF-")},
    ".jpg": {"mime": "image/jpeg", "signature": lambda content: content.startswith(b"\xff\xd8\xff")},
    ".jpeg": {"mime": "image/jpeg", "signature": lambda content: content.startswith(b"\xff\xd8\xff")},
    ".png": {"mime": "image/png", "signature": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n")},
}


async def _read_and_validate_upload(upload: UploadFile, document_type: str) -> tuple[bytes, str]:
    normalized_type = document_type.strip().lower()
    if normalized_type not in SUPPORTED_DOCUMENT_TYPES or len(normalized_type) > MAX_DOCUMENT_TYPE_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported document type")

    filename = upload.filename or ""
    extension = PurePosixPath(filename).suffix.lower()
    rule = _FILE_RULES.get(extension)
    if rule is None or upload.content_type != rule["mime"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported document format")

    content = bytearray()
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.document_max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document is too large")

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document file is empty")
    if not rule["signature"](bytes(content)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document content is invalid")
    return bytes(content), extension


async def create_identity_verification(
    db: Session,
    user: User,
    upload: UploadFile,
    document_type: str,
    storage: PrivateObjectStorage,
) -> IdentityVerification:
    content, extension = await _read_and_validate_upload(upload, document_type)
    object_key = f"documents/{uuid.uuid4().hex}{extension}"
    try:
        storage.put_object(object_key, content, upload.content_type or "application/octet-stream")
    except StorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        ) from None

    verification = IdentityVerification(
        user_id=user.id,
        document_type=document_type.strip().lower(),
        document_storage_key=object_key,
        status="PENDING",
        reason_code="uploaded_pending_processing",
    )
    db.add(verification)
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
            detail="Document processing request could not be recorded",
        ) from None


def get_owned_identity_verification(db: Session, user: User, verification_id: uuid.UUID) -> IdentityVerification:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document verification not found")
    return verification
