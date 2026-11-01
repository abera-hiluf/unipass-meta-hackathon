"""Persist local identity-demo email confirmation per user.

Revision ID: 0013_demo_email_confirmation
Revises: 0012_identity_demo_bypass
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013_demo_email_confirmation"
down_revision: str | None = "0012_identity_demo_bypass"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("demo_email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("demo_email_confirmed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "demo_email_confirmed_at")
    op.drop_column("users", "demo_email")
