"""Add liveness challenge and assessment tracking.

Revision ID: 0008_liveness_tracking
Revises: 0007_selfie_capture
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_liveness_tracking"
down_revision: str | None = "0007_selfie_capture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("identity_verifications", sa.Column("liveness_status", sa.String(length=32), nullable=False, server_default="NOT_STARTED"))
    op.add_column("identity_verifications", sa.Column("liveness_capture_storage_key", sa.String(length=512), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_challenge_hash", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_challenge_steps", sa.String(length=255), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_challenge_issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_challenge_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_challenge_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_reason_code", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("liveness_provider", sa.String(length=128), nullable=True))
    op.create_check_constraint(
        "ck_identity_verifications_liveness_status",
        "identity_verifications",
        "liveness_status IN ('NOT_STARTED', 'CHALLENGE_ISSUED', 'PROCESSING', 'LIVE', 'SPOOF_SUSPECTED', 'REVIEW_REQUIRED', 'FAILED')",
    )
    op.create_index("ix_identity_verifications_liveness_status", "identity_verifications", ["liveness_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_identity_verifications_liveness_status", table_name="identity_verifications")
    op.drop_constraint("ck_identity_verifications_liveness_status", "identity_verifications", type_="check")
    for column in (
        "liveness_provider", "liveness_reason_code", "liveness_completed_at", "liveness_started_at",
        "liveness_consent_at", "liveness_challenge_used_at", "liveness_challenge_expires_at",
        "liveness_challenge_issued_at", "liveness_challenge_steps", "liveness_challenge_hash",
        "liveness_capture_storage_key", "liveness_status",
    ):
        op.drop_column("identity_verifications", column)
