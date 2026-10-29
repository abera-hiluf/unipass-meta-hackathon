"""Add institutions, affiliations, and email verification challenges.

Revision ID: 0004_institution_email_verification
Revises: 0003_add_user_hashed_password
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_institution_email_verification"
down_revision: str | None = "0003_add_user_hashed_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PILOT_INSTITUTION_ID = "00000000-0000-0000-0000-000000000004"


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("official_display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_development_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_institutions_slug", "institutions", ["slug"], unique=False)

    op.create_table(
        "institution_email_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "domain", name="uq_institution_email_domain"),
    )
    op.create_index("ix_institution_email_domains_institution_id", "institution_email_domains", ["institution_id"], unique=False)

    op.create_table(
        "institution_affiliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institutional_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="email_not_verified"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('email_not_verified', 'email_verified', 'enrollment_pending', 'enrollment_confirmed', 'enrollment_rejected', 'enrollment_revoked')",
            name="ck_institution_affiliation_status",
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "institution_id", name="uq_user_institution_affiliation"),
        sa.UniqueConstraint("institution_id", "institutional_email", name="uq_institutional_email"),
    )
    op.create_index("ix_institution_affiliations_user_id", "institution_affiliations", ["user_id"], unique=False)
    op.create_index("ix_institution_affiliations_institution_id", "institution_affiliations", ["institution_id"], unique=False)

    op.create_table(
        "email_verification_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("affiliation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["affiliation_id"], ["institution_affiliations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_email_verification_challenges_affiliation_id", "email_verification_challenges", ["affiliation_id"], unique=False)
    op.create_index("ix_email_verification_challenges_expires_at", "email_verification_challenges", ["expires_at"], unique=False)
    op.create_index("ix_email_verification_challenges_token_hash", "email_verification_challenges", ["token_hash"], unique=False)

    # Development-only pilot configuration. No institutional email domain is
    # inserted because no authorized source has confirmed one.
    op.execute(
        sa.text(
            "INSERT INTO institutions (id, slug, official_display_name, is_active, is_development_only) "
            "VALUES (:id, :slug, :display_name, TRUE, TRUE)"
        ).bindparams(
            id=PILOT_INSTITUTION_ID,
            slug="anna-university-bit-campus-development",
            display_name="Anna University, BIT Campus, Tiruchirappalli",
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM institutions WHERE id = :id").bindparams(id=PILOT_INSTITUTION_ID))
    op.drop_index("ix_email_verification_challenges_token_hash", table_name="email_verification_challenges")
    op.drop_index("ix_email_verification_challenges_expires_at", table_name="email_verification_challenges")
    op.drop_index("ix_email_verification_challenges_affiliation_id", table_name="email_verification_challenges")
    op.drop_table("email_verification_challenges")
    op.drop_index("ix_institution_affiliations_institution_id", table_name="institution_affiliations")
    op.drop_index("ix_institution_affiliations_user_id", table_name="institution_affiliations")
    op.drop_table("institution_affiliations")
    op.drop_index("ix_institution_email_domains_institution_id", table_name="institution_email_domains")
    op.drop_table("institution_email_domains")
    op.drop_index("ix_institutions_slug", table_name="institutions")
    op.drop_table("institutions")
