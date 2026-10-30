"""Add document analysis tracking and extraction references.

Revision ID: 0006_document_analysis
Revises: 0005_add_eligibility_tracking
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_document_analysis"
down_revision: str | None = "0005_add_eligibility_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_identity_verifications_status", "identity_verifications", type_="check")
    op.create_check_constraint(
        "ck_identity_verifications_status",
        "identity_verifications",
        "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'RETRY_REQUIRED', 'FAILED', 'FLAGGED', 'APPROVED', 'REJECTED')",
    )
    op.add_column("identity_verifications", sa.Column("analysis_source", sa.String(length=128), nullable=True))
    op.add_column("identity_verifications", sa.Column("analysis_reason_code", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("analysis_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("extracted_full_name", sa.String(length=255), nullable=True))
    op.add_column("identity_verifications", sa.Column("extracted_date_of_birth", sa.Date(), nullable=True))
    op.add_column("identity_verifications", sa.Column("document_number_hmac", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("extraction_confidence", sa.Float(), nullable=True))
    op.add_column("identity_verifications", sa.Column("portrait_storage_key", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("identity_verifications", "portrait_storage_key")
    op.drop_column("identity_verifications", "extraction_confidence")
    op.drop_column("identity_verifications", "document_number_hmac")
    op.drop_column("identity_verifications", "extracted_date_of_birth")
    op.drop_column("identity_verifications", "extracted_full_name")
    op.drop_column("identity_verifications", "analysis_completed_at")
    op.drop_column("identity_verifications", "analysis_started_at")
    op.drop_column("identity_verifications", "analysis_reason_code")
    op.drop_column("identity_verifications", "analysis_source")
    op.drop_constraint("ck_identity_verifications_status", "identity_verifications", type_="check")
    op.create_check_constraint(
        "ck_identity_verifications_status",
        "identity_verifications",
        "status IN ('PENDING', 'APPROVED', 'FLAGGED', 'REJECTED')",
    )
