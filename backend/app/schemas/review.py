from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IdentityReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject|resubmit)$")
    reason: str = Field(min_length=3, max_length=512)


class IdentityReviewResponse(BaseModel):
    verification_id: UUID
    outcome: str
    status: str
    reason: str
    reviewed_at: datetime


class IdentityStatusResponse(BaseModel):
    verification_id: UUID | None
    outcome: str
    verification_status: str | None
    affiliation_statuses: list[str]
    liveness_status: str | None
    face_match_status: str | None
    document_analysis_status: str | None
