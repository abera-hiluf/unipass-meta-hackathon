import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditLog, IdentityVerification, StudentProfile, User


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_metadata_contains_expected_tables_and_relationship_constraints() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "student_profiles",
        "identity_verifications",
        "audit_logs",
        "institutions",
        "institution_email_domains",
        "institution_affiliations",
        "email_verification_challenges",
    }
    assert User.__table__.c.id.type.as_uuid is True
    assert StudentProfile.__table__.c.user_id.foreign_keys
    assert IdentityVerification.__table__.c.user_id.foreign_keys
    assert IdentityVerification.__table__.c.reviewed_by.foreign_keys
    assert AuditLog.__table__.c.actor_user_id.foreign_keys


def test_email_is_normalized_and_unique(session: Session) -> None:
    first = User(email="  Student@Example.COM ")
    session.add(first)
    session.commit()

    assert first.email == "student@example.com"

    session.add(User(email="STUDENT@example.com"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_uuid_keys_and_student_id_uniqueness(session: Session) -> None:
    first_user = User(email="first@example.com")
    second_user = User(email="second@example.com")
    session.add_all([first_user, second_user])
    session.flush()

    profile = StudentProfile(
        user_id=first_user.id,
        student_id="S-100",
        first_name="First",
        last_name="Student",
        university="Example University",
    )
    session.add(profile)
    session.commit()

    assert isinstance(first_user.id, uuid.UUID)
    assert isinstance(profile.id, uuid.UUID)

    session.add(
        StudentProfile(
            user_id=second_user.id,
            student_id="S-100",
            first_name="Second",
            last_name="Student",
            university="Example University",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_verification_status_check_constraint(session: Session) -> None:
    user = User(email="student@example.com")
    session.add(user)
    session.flush()
    session.add(IdentityVerification(user_id=user.id, status="unknown"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_alembic_revision_defines_all_tables() -> None:
    migration = Path("alembic/versions/0001_initial_models.py").read_text(encoding="utf-8")
    for table_name in ("users", "student_profiles", "identity_verifications", "audit_logs"):
        assert f'"{table_name}"' in migration
