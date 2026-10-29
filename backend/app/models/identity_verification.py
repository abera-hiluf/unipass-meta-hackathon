from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import Uuid

from app.db import Base
from app.models.enums import VERIFICATION_STATUSES, VerificationStatus

if TYPE_CHECKING:
    from app.models.user import User


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"
    __table_args__ = (
        CheckConstraint(
            f"status IN {VERIFICATION_STATUSES}",
            name="ck_identity_verifications_status",
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
