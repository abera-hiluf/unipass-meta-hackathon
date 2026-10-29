from pydantic import BaseModel, Field


class EligibilityVerificationRequest(BaseModel):
    student_identifier: str = Field(..., min_length=1, max_length=128)


class EligibilityVerificationResponse(BaseModel):
    status: str
    outcome: str
    reason_code: str
    source: str
