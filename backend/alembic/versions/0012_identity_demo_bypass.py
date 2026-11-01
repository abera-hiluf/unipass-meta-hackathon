"""Record development identity demo email-verification bypasses.

Revision ID: 0012_identity_demo_bypass
Revises: 0011_document_metadata
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_identity_demo_bypass"
down_revision: str | None = "0011_document_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "identity_verifications",
        sa.Column("email_verification_bypassed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("identity_verifications", "email_verification_bypassed")
