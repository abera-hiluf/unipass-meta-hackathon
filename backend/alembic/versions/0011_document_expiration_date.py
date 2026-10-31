"""Persist extracted document metadata.

Revision ID: 0011_document_metadata
Revises: 0010_email_ownership
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_document_metadata"
down_revision: str | None = "0010_email_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "identity_verifications",
        sa.Column("extracted_expiration_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "identity_verifications",
        sa.Column("extracted_document_type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("identity_verifications", "extracted_document_type")
    op.drop_column("identity_verifications", "extracted_expiration_date")
