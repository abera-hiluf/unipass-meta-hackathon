"""Add institution eligibility tracking fields.

Revision ID: 0005_add_eligibility_tracking
Revises: 0004_institution_email_verification
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_eligibility_tracking"
down_revision: str | None = "0004_institution_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("institution_affiliations", sa.Column("eligibility_source", sa.String(length=128), nullable=True))
    op.add_column("institution_affiliations", sa.Column("eligibility_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("institution_affiliations", sa.Column("eligibility_reason_code", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_institution_affiliations_eligibility_checked_at",
        "institution_affiliations",
        ["eligibility_checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_institution_affiliations_eligibility_checked_at", table_name="institution_affiliations")
    op.drop_column("institution_affiliations", "eligibility_reason_code")
    op.drop_column("institution_affiliations", "eligibility_checked_at")
    op.drop_column("institution_affiliations", "eligibility_source")
