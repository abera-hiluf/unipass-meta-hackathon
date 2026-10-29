from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.email_verification import EmailVerificationChallenge
    from app.models.user import User


AFFILIATION_STATUSES = (
    "email_not_verified",
    "email_verified",
    "enrollment_pending",
    "enrollment_confirmed",
    "enrollment_rejected",
    "enrollment_revoked",
)

VALID_AFFILIATION_TRANSITIONS = {
    "email_not_verified": {"email_verified"},
    "email_verified": {"enrollment_pending"},
    "enrollment_pending": {"enrollment_confirmed", "enrollment_rejected"},
    "enrollment_confirmed": {"enrollment_revoked"},
    "enrollment_rejected": {"enrollment_pending"},
    "enrollment_revoked": {"enrollment_pending"},
}


class InstitutionAffiliation(Base):
    __tablename__ = "institution_affiliations"
    __table_args__ = (
        UniqueConstraint("user_id", "institution_id", name="uq_user_institution_affiliation"),
        UniqueConstraint("institution_id", "institutional_email", name="uq_institutional_email"),
        CheckConstraint(
            "status IN ('email_not_verified', 'email_verified', 'enrollment_pending', "
            "'enrollment_confirmed', 'enrollment_rejected', 'enrollment_revoked')",
            name="ck_institution_affiliation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institutional_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="email_not_verified")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eligibility_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eligibility_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eligibility_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="institution_affiliations")
    institution: Mapped[Institution] = relationship(back_populates="affiliations")
    verification_challenges: Mapped[list[EmailVerificationChallenge]] = relationship(
        back_populates="affiliation", cascade="all, delete-orphan"
    )

    def transition_to(self, new_status: str) -> None:
        if new_status not in AFFILIATION_STATUSES:
            raise ValueError("Unsupported affiliation status")
        if new_status == self.status:
            return
        if new_status not in VALID_AFFILIATION_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid affiliation transition: {self.status} -> {new_status}")
        self.status = new_status
