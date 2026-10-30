from datetime import datetime
import uuid

from pydantic import BaseModel


class SelfieSubmissionResponse(BaseModel):
    verification_id: uuid.UUID
    selfie_status: str
    selfie_reason_code: str | None
    selfie_submitted_at: datetime | None
