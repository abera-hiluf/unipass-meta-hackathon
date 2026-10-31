from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters")
    role: str = Field(default="student", description="Public registration is limited to student accounts")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().casefold()
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned != "student":
            raise ValueError("Public registration is limited to student accounts")
        return cleaned


class UserLoginRequest(BaseModel):
    """Schema for user login credentials."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().casefold()
        return v


class TokenResponse(BaseModel):
    """Schema for JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Safe schema for user account details without password hashes."""

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailOwnershipCodeRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().casefold()
        return value


class EmailOwnershipConfirmRequest(BaseModel):
    code: str = Field(..., pattern=r"^[0-9]{6}$")


class EmailOwnershipStatusResponse(BaseModel):
    status: str
    email: EmailStr | None
    verified_email: EmailStr | None
    expires_at: datetime | None
    resend_available_at: datetime | None
