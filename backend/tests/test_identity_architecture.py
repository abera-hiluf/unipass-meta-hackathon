import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import compute_document_fingerprint, normalize_document_identifier
from app.db import Base
from app.models import (
    AuditLog,
    IdentityVerification,
    StudentProfile,
    User,
    VerificationStatus,
    VERIFICATION_STATUSES,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_student_profile_verified_attributes(session: Session) -> None:
    user = User(email="student.identity@university.edu")
    session.add(user)
    session.flush()

    dob = date(2003, 5, 14)
    fingerprint = compute_document_fingerprint("P-987654321", secret="test-secret-key")

    profile = StudentProfile(
        user_id=user.id,
        student_id="STU-2026-001",
        first_name="Ada",
        last_name="Lovelace",
        university="University of Technology",
        date_of_birth=dob,
        document_type="passport",
        document_identifier_hash=fingerprint,
        verification_status=VerificationStatus.PENDING,
    )
    session.add(profile)
    session.commit()

    saved_profile = session.get(StudentProfile, profile.id)
    assert saved_profile is not None
    assert saved_profile.full_name == "Ada Lovelace"
    assert saved_profile.date_of_birth == dob
    assert saved_profile.document_type == "passport"
    assert saved_profile.document_identifier_hash == fingerprint
    assert saved_profile.verification_status == "PENDING"
    assert saved_profile.verified_at is None
    assert saved_profile.created_at is not None
    assert saved_profile.updated_at is not None


def test_verification_status_lifecycle_support(session: Session) -> None:
    user = User(email="status.test@university.edu")
    session.add(user)
    session.flush()

    # Test all 4 valid lifecycle statuses
    for status_val in (
        VerificationStatus.PENDING,
        VerificationStatus.APPROVED,
        VerificationStatus.FLAGGED,
        VerificationStatus.REJECTED,
    ):
        verification = IdentityVerification(
            user_id=user.id,
            status=status_val,
        )
        session.add(verification)
    session.commit()

    # Case normalization check
    normalized_verif = IdentityVerification(user_id=user.id, status="approved")
    assert normalized_verif.status == "APPROVED"

    # Invalid status should be rejected by constraint
    session.add(IdentityVerification(user_id=user.id, status="INVALID_STATUS"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_document_hmac_fingerprint_security() -> None:
    raw_doc = "  ab-123 456 789  "
    normalized = normalize_document_identifier(raw_doc)
    assert normalized == "AB123456789"

    secret_one = "secret-key-alpha"
    secret_two = "secret-key-beta"

    hash_one = compute_document_fingerprint(raw_doc, secret=secret_one)
    hash_two = compute_document_fingerprint(raw_doc, secret=secret_two)

    # Keyed HMAC must differ when keys differ (salted by server secret)
    assert hash_one != hash_two

    # Formatting invariance: spaces and lowercase must result in the identical fingerprint
    identical_hash = compute_document_fingerprint("AB123456789", secret=secret_one)
    assert hash_one == identical_hash

    # Raw doc number must never appear in the hash
    assert raw_doc.strip() not in hash_one


def test_multiple_verification_attempts_without_overwriting(session: Session) -> None:
    student = User(email="applicant@university.edu")
    reviewer = User(email="admin.officer@university.edu", role="admin")
    session.add_all([student, reviewer])
    session.flush()

    # Attempt 1: Rejected due to blurry photo / expired document
    attempt_one = IdentityVerification(
        user_id=student.id,
        status=VerificationStatus.REJECTED,
        document_type="national_id",
        document_storage_key="secure-vault/docs/attempt-1.enc",
        reason_code="EXPIRED_DOCUMENT",
        review_notes="The national ID provided expired on 2024-01-01.",
        reviewed_by=reviewer.id,
        reviewed_at=datetime.now(timezone.utc),
    )
    session.add(attempt_one)
    session.commit()

    # Attempt 2: Student retries with renewed passport
    attempt_two = IdentityVerification(
        user_id=student.id,
        status=VerificationStatus.PENDING,
        document_type="passport",
        document_storage_key="secure-vault/docs/attempt-2.enc",
    )
    session.add(attempt_two)
    session.commit()

    # Reviewer approves Attempt 2
    attempt_two.status = VerificationStatus.APPROVED
    attempt_two.reviewed_by = reviewer.id
    attempt_two.reviewed_at = datetime.now(timezone.utc)
    attempt_two.reason_code = "VERIFIED_VALID"
    session.commit()

    # Verify history is preserved: both attempts exist linked to student
    refreshed_student = session.get(User, student.id)
    assert refreshed_student is not None
    assert len(refreshed_student.verification_attempts) == 2

    statuses = [a.status for a in refreshed_student.verification_attempts]
    assert "REJECTED" in statuses
    assert "APPROVED" in statuses

    # Check reason codes and private storage keys are preserved
    rejected = next(a for a in refreshed_student.verification_attempts if a.status == "REJECTED")
    approved = next(a for a in refreshed_student.verification_attempts if a.status == "APPROVED")

    assert rejected.reason_code == "EXPIRED_DOCUMENT"
    assert rejected.document_storage_key == "secure-vault/docs/attempt-1.enc"
    assert approved.reason_code == "VERIFIED_VALID"
    assert approved.document_storage_key == "secure-vault/docs/attempt-2.enc"


def test_audit_record_integrity(session: Session) -> None:
    admin = User(email="auditor@university.edu", role="admin")
    session.add(admin)
    session.flush()

    # 1. Admin status change audit
    log_one = AuditLog(
        actor_user_id=admin.id,
        action="IDENTITY_VERIFICATION_STATUS_CHANGED",
        resource_type="identity_verifications",
        resource_id=str(uuid.uuid4()),
        details={
            "old_status": "PENDING",
            "new_status": "APPROVED",
            "reason_code": "VERIFIED_VALID",
        },
    )
    session.add(log_one)

    # 2. AgentX tool execution audit
    log_two = AuditLog(
        actor_user_id=admin.id,
        action="AGENTX_TOOL_INVOKED",
        resource_type="campus_service",
        resource_id="library_service",
        details={
            "tool_name": "check_borrowing_status",
            "scope": "library:read",
        },
    )
    session.add(log_two)
    session.commit()

    saved_logs = session.query(AuditLog).all()
    assert len(saved_logs) == 2
    assert saved_logs[0].details["new_status"] == "APPROVED"
    assert saved_logs[1].details["tool_name"] == "check_borrowing_status"

    # Verify no raw documents or sensitive credentials can be extracted from logs
    log_text = str([l.details for l in saved_logs])
    assert "password" not in log_text
    assert "token" not in log_text


def test_downstream_service_separation_from_identity() -> None:
    """Ensure StudentProfile does NOT contain domain-specific data from campus services

    (e.g. library cards, fines, health allergies, blood groups).
    """
    profile_columns = {col.name for col in StudentProfile.__table__.columns}

    # Library service specific fields must not be on StudentProfile
    forbidden_library_fields = {"library_card_number", "borrowing_limit", "outstanding_fines"}
    assert not (profile_columns & forbidden_library_fields)

    # Health service specific fields must not be on StudentProfile
    forbidden_health_fields = {"blood_group", "allergy_information", "emergency_contact"}
    assert not (profile_columns & forbidden_health_fields)


def test_alembic_revision_0002_defines_centralized_identity_ddl() -> None:
    migration_file = Path("alembic/versions/0002_centralized_identity.py")
    assert migration_file.exists()

    content = migration_file.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0001_initial_models"' in content
    assert '"date_of_birth"' in content
    assert '"document_type"' in content
    assert '"document_identifier_hash"' in content
    assert '"verification_status"' in content
    assert '"document_storage_key"' in content
    assert '"reason_code"' in content
    assert '"details"' in content
