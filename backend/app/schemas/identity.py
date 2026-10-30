from datetime import date, datetime
import uuid

from pydantic import BaseModel


class IdentityDocumentResponse(BaseModel):
    id: uuid.UUID
    document_type: str
    status: str
    reason_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    analysis_source: str | None = None
    analysis_reason_code: str | None = None
    analysis_started_at: datetime | None = None
    analysis_completed_at: datetime | None = None
    extracted_full_name: str | None = None
    extracted_date_of_birth: date | None = None
    extraction_confidence: float | None = None
    portrait_available: bool = False
