from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FaceMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_id: UUID
    status: str
    reason_code: str | None
    provider: str | None
    completed_at: datetime | None
