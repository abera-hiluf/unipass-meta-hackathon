from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import Uuid

from app.db import Base
from app.models.enums import VERIFICATION_STATUSES, VerificationStatus

if TYPE_CHECKING:
    from app.models.user import User


VALID_IDENTITY_VERIFICATION_TRANSITIONS = {
    "PENDING": {"PROCESSING", "FAILED", "RETRY_REQUIRED"},
    "PROCESSING": {"COMPLETED", "RETRY_REQUIRED", "FLAGGED", "FAILED"},
    "RETRY_REQUIRED": {"PROCESSING", "FAILED"},
    "FAILED": {"PROCESSING"},
    "COMPLETED": {"APPROVED", "FLAGGED"},
    "FLAGGED": {"APPROVED", "REJECTED", "PROCESSING"},
    "APPROVED": set(),
    "REJECTED": {"PROCESSING"},
}

SELFIE_STATUSES = ("NOT_SUBMITTED", "SUBMITTED", "RETRY_REQUIRED", "FAILED")


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"
    __table_args__ = (
        CheckConstraint(
            f"status IN {VERIFICATION_STATUSES}",
            name="ck_identity_verifications_status",
        ),
        CheckConstraint(
            f"selfie_status IN {SELFIE_STATUSES}",
            name="ck_identity_verifications_selfie_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=VerificationStatus.PENDING.value,
        server_default=VerificationStatus.PENDING.value,
    )
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    analysis_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    analysis_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_number_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(nullable=True)
    portrait_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selfie_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_SUBMITTED", server_default="NOT_SUBMITTED")
    selfie_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selfie_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selfie_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selfie_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="verification_attempts", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(back_populates="reviewed_verifications", foreign_keys=[reviewed_by])

    @property
    def submitted_at(self) -> datetime:
        return self.created_at

    @validates("status")
    def validate_status(self, _key: str, status: str | VerificationStatus) -> str:
        if isinstance(status, VerificationStatus):
            return status.value
        return status.strip().upper()

    @validates("selfie_status")
    def validate_selfie_status(self, _key: str, selfie_status: str) -> str:
        normalized = selfie_status.strip().upper()
        if normalized not in SELFIE_STATUSES:
            raise ValueError("Unsupported selfie status")
        return normalized

    def transition_to(self, new_status: str | VerificationStatus) -> None:
        target = new_status.value if isinstance(new_status, VerificationStatus) else new_status.strip().upper()
        if target not in VERIFICATION_STATUSES:
            raise ValueError("Unsupported identity verification status")
        if target == self.status:
            return
        if target not in VALID_IDENTITY_VERIFICATION_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid identity verification transition: {self.status} -> {target}")
        self.status = target
