from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, validates, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.identity_verification import IdentityVerification
    from app.models.institution_affiliation import InstitutionAffiliation
    from app.models.student_profile import StudentProfile


SUPPORTED_ROLES = ("student", "admin")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped[StudentProfile | None] = relationship(back_populates="user", uselist=False)
    verification_attempts: Mapped[list[IdentityVerification]] = relationship(
        back_populates="user", foreign_keys="IdentityVerification.user_id"
    )
    reviewed_verifications: Mapped[list[IdentityVerification]] = relationship(
        back_populates="reviewer", foreign_keys="IdentityVerification.reviewed_by"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    institution_affiliations: Mapped[list[InstitutionAffiliation]] = relationship(back_populates="user")

    @validates("email")
    def validate_email(self, _key: str, email: str) -> str:
        return normalize_email(email)
