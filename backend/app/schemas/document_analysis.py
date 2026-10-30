from datetime import date, datetime

from pydantic import BaseModel


class DocumentAnalysisResponse(BaseModel):
    status: str
    reason_code: str
    source: str
    analysis_started_at: datetime | None
    analysis_completed_at: datetime | None
    extracted_full_name: str | None
    extracted_date_of_birth: date | None
    extraction_confidence: float | None
    portrait_available: bool
