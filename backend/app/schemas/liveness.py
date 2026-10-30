from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LivenessChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_id: UUID
    challenge_id: str
    steps: list[str]
    expires_at: datetime
    liveness_status: str


class LivenessResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_id: UUID
    liveness_status: str
    reason_code: str | None
    provider: str | None
    completed_at: datetime | None
