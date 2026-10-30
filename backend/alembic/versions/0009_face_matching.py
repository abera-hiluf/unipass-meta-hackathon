"""Add face-matching assessment tracking.

Revision ID: 0009_face_matching
Revises: 0008_liveness_tracking
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_face_matching"
down_revision: str | None = "0008_liveness_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("identity_verifications", sa.Column("face_match_status", sa.String(length=32), nullable=False, server_default="NOT_STARTED"))
    op.add_column("identity_verifications", sa.Column("face_match_score", sa.Float(), nullable=True))
    op.add_column("identity_verifications", sa.Column("face_match_reason_code", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("face_match_provider", sa.String(length=128), nullable=True))
    op.add_column("identity_verifications", sa.Column("face_match_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("face_match_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_identity_verifications_face_match_status",
        "identity_verifications",
        "face_match_status IN ('NOT_STARTED', 'PROCESSING', 'MATCH', 'NO_MATCH', 'REVIEW_REQUIRED', 'FAILED')",
    )
    op.create_index("ix_identity_verifications_face_match_status", "identity_verifications", ["face_match_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_identity_verifications_face_match_status", table_name="identity_verifications")
    op.drop_constraint("ck_identity_verifications_face_match_status", "identity_verifications", type_="check")
    for column in ("face_match_completed_at", "face_match_started_at", "face_match_provider", "face_match_reason_code", "face_match_score", "face_match_status"):
        op.drop_column("identity_verifications", column)
