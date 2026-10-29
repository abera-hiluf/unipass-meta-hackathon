"""Align models with centralized identity registry architecture.

Revision ID: 0002_centralized_identity
Revises: 0001_initial_models
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_centralized_identity"
down_revision: str | None = "0001_initial_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. student_profiles: add verified identity attributes
    op.add_column("student_profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("student_profiles", sa.Column("document_type", sa.String(length=64), nullable=True))
    op.add_column("student_profiles", sa.Column("document_identifier_hash", sa.String(length=128), nullable=True))
    op.add_column(
        "student_profiles",
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="PENDING"),
    )
    op.add_column("student_profiles", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_student_profiles_doc_hash", "student_profiles", ["document_identifier_hash"], unique=False
    )
    op.create_check_constraint(
        "ck_student_profiles_verification_status",
        "student_profiles",
        "verification_status IN ('PENDING', 'APPROVED', 'FLAGGED', 'REJECTED')",
    )

    # 2. identity_verifications: add outcome tracking, private document storage references, and align status lifecycle
    op.add_column("identity_verifications", sa.Column("document_type", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("document_storage_key", sa.String(length=512), nullable=True))
    op.add_column("identity_verifications", sa.Column("reason_code", sa.String(length=64), nullable=True))
    op.add_column("identity_verifications", sa.Column("review_notes", sa.String(length=512), nullable=True))
    op.alter_column("identity_verifications", "status", server_default="PENDING")

    # Safe status migration: update any existing rows to uppercase before switching constraint
    op.drop_constraint("ck_identity_verifications_status", "identity_verifications", type_="check")
    op.execute("UPDATE identity_verifications SET status = UPPER(status)")
    op.create_check_constraint(
        "ck_identity_verifications_status",
        "identity_verifications",
        "status IN ('PENDING', 'APPROVED', 'FLAGGED', 'REJECTED')",
    )

    # 3. audit_logs: add structured details JSON for non-sensitive event metadata
    op.add_column("audit_logs", sa.Column("details", sa.JSON(), nullable=True))


def downgrade() -> None:
    # 1. audit_logs
    op.drop_column("audit_logs", "details")

    # 2. identity_verifications
    op.drop_constraint("ck_identity_verifications_status", "identity_verifications", type_="check")
    op.create_check_constraint(
        "ck_identity_verifications_status",
        "identity_verifications",
        "status IN ('pending', 'approved', 'rejected')",
    )
    op.alter_column("identity_verifications", "status", server_default="pending")
    op.drop_column("identity_verifications", "review_notes")
    op.drop_column("identity_verifications", "reason_code")
    op.drop_column("identity_verifications", "document_storage_key")
    op.drop_column("identity_verifications", "document_type")

    # 3. student_profiles
    op.drop_constraint("ck_student_profiles_verification_status", "student_profiles", type_="check")
    op.drop_index("ix_student_profiles_doc_hash", table_name="student_profiles")
    op.drop_column("student_profiles", "verified_at")
    op.drop_column("student_profiles", "verification_status")
    op.drop_column("student_profiles", "document_identifier_hash")
    op.drop_column("student_profiles", "document_type")
    op.drop_column("student_profiles", "date_of_birth")
