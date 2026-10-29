from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import normalize_email


class InstitutionResponse(BaseModel):
    id: uuid.UUID
    slug: str
    official_display_name: str
    is_active: bool
    is_development_only: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionEmailVerificationRequest(BaseModel):
    institutional_email: EmailStr

    @field_validator("institutional_email", mode="before")
    @classmethod
    def normalize_institutional_email(cls, value: str) -> str:
        if isinstance(value, str):
            return normalize_email(value)
        return value


class EmailVerificationConfirmRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)


class EmailVerificationResponse(BaseModel):
    detail: str


class AffiliationResponse(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    institution_name: str
    institutional_email: EmailStr
    status: str
    email_verified_at: datetime | None
    eligibility_source: str | None
    eligibility_checked_at: datetime | None
    eligibility_reason_code: str | None
