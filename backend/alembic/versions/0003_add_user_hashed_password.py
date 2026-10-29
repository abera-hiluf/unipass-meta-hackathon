"""Add hashed_password to users.

Revision ID: 0003_add_user_hashed_password
Revises: 0002_centralized_identity
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_user_hashed_password"
down_revision: str | None = "0002_centralized_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=False, server_default=""),
    )
    # Remove server_default so future inserts are required to provide a hashed password
    op.alter_column("users", "hashed_password", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
