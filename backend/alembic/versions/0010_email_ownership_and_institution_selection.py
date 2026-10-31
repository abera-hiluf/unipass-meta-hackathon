"""Add account email ownership and persistent institution selection.

Revision ID: 0010_email_ownership
Revises: 0009_face_matching
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_email_ownership"
down_revision: str | None = "0009_face_matching"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("verified_email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("selected_institution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_users_selected_institution_id_institutions",
        "users",
        "institutions",
        ["selected_institution_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_selected_institution_id", "users", ["selected_institution_id"], unique=False)

    op.create_table(
        "email_ownership_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_ownership_challenges_user_id", "email_ownership_challenges", ["user_id"], unique=False)
    op.create_index("ix_email_ownership_challenges_expires_at", "email_ownership_challenges", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_email_ownership_challenges_expires_at", table_name="email_ownership_challenges")
    op.drop_index("ix_email_ownership_challenges_user_id", table_name="email_ownership_challenges")
    op.drop_table("email_ownership_challenges")
    op.drop_index("ix_users_selected_institution_id", table_name="users")
    op.drop_constraint("fk_users_selected_institution_id_institutions", "users", type_="foreignkey")
    op.drop_column("users", "selected_institution_id")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "verified_email")
