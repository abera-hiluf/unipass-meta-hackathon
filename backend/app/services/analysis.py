from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from datetime import date as date_type
import hashlib
import hmac
from io import BytesIO
import re
from typing import Protocol
import uuid

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.document_validation import validate_document_content
from app.services.meta_api import MetaAPIError, MetaModelClient
from app.services.storage import PrivateObjectStorage, StorageError


class DocumentAnalysisError(RuntimeError):
    """Raised by an analysis adapter when processing cannot continue safely."""


@dataclass(frozen=True)
class DocumentAnalysisResult:
    status: str
    reason_code: str
    source: str
    confidence: float | None = None
    extracted_document_type: str | None = None
    full_name: str | None = None
    date_of_birth: datetime | None = None
    expiration_date: date_type | None = None
    document_number_hmac: str | None = None
    portrait_bytes: bytes | None = None
    portrait_extension: str | None = None
    portrait_content_type: str | None = None


class DocumentAnalysisAdapter(Protocol):
    def analyze(self, content: bytes, document_type: str) -> DocumentAnalysisResult: ...


class UnavailableDocumentAnalysisAdapter:
    """Safe default until an authorized OCR/vision provider is configured."""

    def analyze(self, content: bytes, document_type: str) -> DocumentAnalysisResult:
        return DocumentAnalysisResult(
            status="RETRY_REQUIRED",
            reason_code="analysis_provider_not_configured",
            source="unavailable",
        )


class MockDocumentAnalysisAdapter:
    """Test-only adapter returning explicitly supplied synthetic results."""

    def __init__(self, result: DocumentAnalysisResult | None = None, error: bool = False) -> None:
        self.result = result or DocumentAnalysisResult(
            status="RETRY_REQUIRED", reason_code="synthetic_result_not_configured", source="mock"
        )
        self.error = error

    def analyze(self, content: bytes, document_type: str) -> DocumentAnalysisResult:
        if self.error:
            raise DocumentAnalysisError("synthetic analysis failure")
        return self.result


class MetaDocumentAnalysisAdapter:
    """Muse Spark field extraction adapter; model output remains untrusted evidence."""

    def __init__(self, client: MetaModelClient | None = None) -> None:
        self.client = client or MetaModelClient()

    def analyze(self, content: bytes, document_type: str) -> DocumentAnalysisResult:
        if content.startswith(b"%PDF-"):
            return DocumentAnalysisResult(
                status="RETRY_REQUIRED",
                reason_code="meta_image_input_required",
                source="meta_muse_spark",
            )
        extension = ".png" if content.startswith(b"\x89PNG") else ".jpg"
        mime_type = "image/png" if extension == ".png" else "image/jpeg"
        try:
            fields = self.client.extract_document_fields(content, mime_type, document_type)
        except MetaAPIError:
            raise DocumentAnalysisError("Meta document analysis failed") from None

        extracted_date: date_type | None = None
        if fields.date_of_birth:
            try:
                extracted_date = date_type.fromisoformat(fields.date_of_birth)
            except ValueError:
                extracted_date = None
        expiration_date: date_type | None = None
        if fields.expiration_date:
            try:
                expiration_date = date_type.fromisoformat(fields.expiration_date)
            except ValueError:
                expiration_date = None

        document_number_hmac = None
        if fields.document_number:
            document_number_hmac = hmac.new(
                settings.document_hmac_secret.encode("utf-8"),
                fields.document_number.strip().encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        portrait_bytes = _extract_portrait_crop(content, fields.portrait_bounds)
        return DocumentAnalysisResult(
            status="COMPLETED",
            reason_code="model_extraction_complete",
            source="meta_muse_spark",
            confidence=fields.confidence,
            extracted_document_type=fields.document_type,
            full_name=fields.full_name,
            date_of_birth=extracted_date,
            expiration_date=expiration_date,
            document_number_hmac=document_number_hmac,
            portrait_bytes=portrait_bytes,
            portrait_extension=".jpg" if portrait_bytes else None,
            portrait_content_type="image/jpeg" if portrait_bytes else None,
        )


def get_document_analysis_adapter() -> DocumentAnalysisAdapter:
    if settings.document_analysis_provider.lower() == "meta" and settings.meta_api_key and settings.meta_api_key.get_secret_value():
        return MetaDocumentAnalysisAdapter()
    # Tests can override this dependency with MockDocumentAnalysisAdapter.
    return UnavailableDocumentAnalysisAdapter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _extract_portrait_crop(content: bytes, bounds: list[float] | None) -> bytes | None:
    if bounds is None or len(bounds) != 4:
        return None
    left, top, right, bottom = bounds
    if not (
        0 <= left < right <= 1
        and 0 <= top < bottom <= 1
        and right - left >= 0.05
        and bottom - top >= 0.05
    ):
        return None
    try:
        with Image.open(BytesIO(content)) as source:
            image = source.convert("RGB")
            width, height = image.size
            crop = image.crop((
                round(left * width),
                round(top * height),
                round(right * width),
                round(bottom * height),
            ))
            if crop.width < 32 or crop.height < 32:
                return None
            output = BytesIO()
            crop.save(output, format="JPEG", quality=95)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _response_status(verification: IdentityVerification) -> dict:
    return {
        "status": verification.status,
        "reason_code": verification.analysis_reason_code or verification.reason_code or "not_analyzed",
        "source": verification.analysis_source or "none",
        "analysis_started_at": verification.analysis_started_at,
        "analysis_completed_at": verification.analysis_completed_at,
        "extracted_document_type": verification.extracted_document_type,
        "extracted_full_name": verification.extracted_full_name,
        "extracted_date_of_birth": verification.extracted_date_of_birth,
        "extracted_expiration_date": verification.extracted_expiration_date,
        "extraction_confidence": verification.extraction_confidence,
        "portrait_available": verification.portrait_storage_key is not None,
    }


def start_document_analysis(
    db: Session,
    user: User,
    verification_id: uuid.UUID,
    storage: PrivateObjectStorage,
    adapter: DocumentAnalysisAdapter,
) -> dict:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document verification not found")
    if not verification.document_storage_key or not verification.document_type:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is not ready for analysis")
    if verification.status not in {"PENDING", "RETRY_REQUIRED", "FAILED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document analysis cannot be restarted")

    try:
        content = storage.get_object(verification.document_storage_key)
    except StorageError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document storage is unavailable") from None

    extension = "." + verification.document_storage_key.rsplit(".", 1)[-1].lower()
    try:
        validate_document_content(content, extension)
    except StorageError:
        verification.analysis_source = "local_validation"
        verification.analysis_reason_code = "document_unreadable"
        verification.analysis_started_at = _now()
        verification.analysis_completed_at = _now()
        verification.transition_to("PROCESSING")
        verification.transition_to("FAILED")
        db.commit()
        return _response_status(verification)

    started_at = _now()
    portrait_key: str | None = None
    try:
        verification.transition_to("PROCESSING")
        verification.analysis_started_at = started_at
        verification.analysis_reason_code = None
        db.flush()
        result = adapter.analyze(content, verification.document_type)

        allowed_statuses = {"COMPLETED", "RETRY_REQUIRED", "FLAGGED", "FAILED"}
        target_status = result.status.upper()
        if target_status not in allowed_statuses:
            raise DocumentAnalysisError("analysis adapter returned an unsupported status")
        if result.confidence is not None and not 0 <= result.confidence <= 1:
            raise DocumentAnalysisError("analysis adapter returned invalid confidence")
        if result.document_number_hmac is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", result.document_number_hmac):
            raise DocumentAnalysisError("analysis adapter returned an invalid document fingerprint")

        if result.portrait_bytes is not None:
            portrait_extension = result.portrait_extension or ".jpg"
            if portrait_extension not in {".jpg", ".jpeg", ".png"}:
                raise DocumentAnalysisError("analysis adapter returned an unsupported portrait format")
            try:
                validate_document_content(result.portrait_bytes, portrait_extension)
            except StorageError as exc:
                raise DocumentAnalysisError("portrait_not_found") from exc
            portrait_key = f"documents/portraits/{uuid.uuid4().hex}{portrait_extension}"
            try:
                storage.put_object(
                    portrait_key,
                    result.portrait_bytes,
                    result.portrait_content_type or "image/jpeg",
                )
            except StorageError:
                verification.analysis_source = result.source
                verification.analysis_reason_code = "portrait_storage_failed"
                verification.analysis_completed_at = _now()
                verification.transition_to("FAILED")
                db.commit()
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Portrait storage is unavailable") from None
            verification.portrait_storage_key = portrait_key

        verification.analysis_source = result.source
        verification.analysis_reason_code = result.reason_code
        verification.extracted_document_type = _safe_name(result.extracted_document_type)
        verification.extracted_full_name = _safe_name(result.full_name)
        verification.extracted_date_of_birth = result.date_of_birth.date() if isinstance(result.date_of_birth, datetime) else result.date_of_birth
        verification.extracted_expiration_date = result.expiration_date
        verification.document_number_hmac = result.document_number_hmac.lower() if result.document_number_hmac else None
        verification.extraction_confidence = result.confidence
        verification.analysis_completed_at = _now()
        verification.transition_to(target_status)
        db.commit()
        return _response_status(verification)
    except DocumentAnalysisError:
        db.rollback()
        verification = db.get(IdentityVerification, verification_id)
        if portrait_key:
            try:
                storage.delete_object(portrait_key)
            except StorageError:
                pass
        if verification is not None:
            verification.analysis_source = "adapter"
            verification.analysis_reason_code = "analysis_failed"
            verification.analysis_started_at = verification.analysis_started_at or started_at
            verification.analysis_completed_at = _now()
            if verification.status != "FAILED":
                verification.transition_to("FAILED")
            db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document analysis is unavailable") from None
    except SQLAlchemyError:
        db.rollback()
        if portrait_key:
            try:
                storage.delete_object(portrait_key)
            except StorageError:
                pass
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document analysis could not be recorded") from None
