"""Add private selfie submission tracking.

Revision ID: 0007_selfie_capture
Revises: 0006_document_analysis
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_selfie_capture"
down_revision: str | None = "0006_document_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "identity_verifications",
        sa.Column("selfie_status", sa.String(length=32), nullable=False, server_default="NOT_SUBMITTED"),
    )
    op.add_column("identity_verifications", sa.Column("selfie_storage_key", sa.String(length=512), nullable=True))
    op.add_column("identity_verifications", sa.Column("selfie_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("selfie_submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("selfie_reason_code", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        "ck_identity_verifications_selfie_status",
        "identity_verifications",
        "selfie_status IN ('NOT_SUBMITTED', 'SUBMITTED', 'RETRY_REQUIRED', 'FAILED')",
    )
    op.create_index(
        "ix_identity_verifications_selfie_status",
        "identity_verifications",
        ["selfie_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_identity_verifications_selfie_status", table_name="identity_verifications")
    op.drop_constraint("ck_identity_verifications_selfie_status", "identity_verifications", type_="check")
    op.drop_column("identity_verifications", "selfie_reason_code")
    op.drop_column("identity_verifications", "selfie_submitted_at")
    op.drop_column("identity_verifications", "selfie_consent_at")
    op.drop_column("identity_verifications", "selfie_storage_key")
    op.drop_column("identity_verifications", "selfie_status")
