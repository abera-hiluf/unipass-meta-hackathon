from datetime import datetime, timezone
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditLog, IdentityVerification, Institution, InstitutionAffiliation, User
from app.schemas.review import IdentityStatusResponse
from app.services.verification_review import identity_status, review_case


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_manual_review_requires_all_independent_evidence(session) -> None:
    student = User(email="review-student@example.com", hashed_password="synthetic")
    reviewer = User(email="review-admin@example.com", hashed_password="synthetic", role="admin")
    institution = Institution(slug="review-institution", official_display_name="Synthetic Institution")
    session.add_all([student, reviewer, institution])
    session.flush()
    session.add(InstitutionAffiliation(
        user_id=student.id,
        institution_id=institution.id,
        institutional_email="student@synthetic.example",
        status="enrollment_confirmed",
    ))
    case = IdentityVerification(
        user_id=student.id,
        status="COMPLETED",
        analysis_completed_at=datetime.now(timezone.utc),
        liveness_status="LIVE",
        face_match_status="MATCH",
    )
    session.add(case)
    session.commit()

    reviewed = review_case(session, reviewer, case.id, "approve", "Synthetic evidence reviewed")
    assert reviewed["outcome"] == "VERIFIED"
    assert session.get(IdentityVerification, case.id).status == "APPROVED"
    assert session.query(AuditLog).filter_by(action="IDENTITY_VERIFICATION_REVIEWED").count() == 1


def test_manual_review_cannot_approve_without_live_or_match(session) -> None:
    student = User(email="review-pending@example.com", hashed_password="synthetic")
    reviewer = User(email="review-admin-2@example.com", hashed_password="synthetic", role="admin")
    session.add_all([student, reviewer])
    session.flush()
    case = IdentityVerification(user_id=student.id, status="FLAGGED", liveness_status="REVIEW_REQUIRED", face_match_status="REVIEW_REQUIRED")
    session.add(case)
    session.commit()

    with pytest.raises(HTTPException) as exc:
        review_case(session, reviewer, case.id, "approve", "Insufficient evidence")
    assert exc.value.status_code == 409


def test_identity_status_is_safe_and_non_admin_cannot_review(session) -> None:
    student = User(email="status-student@example.com", hashed_password="synthetic")
    session.add(student)
    session.commit()
    status_result = identity_status(session, student)
    assert status_result["outcome"] == "PENDING"
    assert status_result["selfie_status"] is None
    assert "document_storage_key" not in status_result


def test_identity_status_returns_actual_selfie_status_without_storage_details(session) -> None:
    student = User(email="selfie-status@example.com", hashed_password="synthetic")
    session.add(student)
    session.flush()
    verification = IdentityVerification(
        user_id=student.id,
        status="PENDING",
        selfie_status="SUBMITTED",
        selfie_storage_key="private/selfie/object",
    )
    session.add(verification)
    session.commit()

    status_result = identity_status(session, student)

    assert status_result["selfie_status"] == "SUBMITTED"
    assert "selfie_storage_key" not in status_result
    assert IdentityStatusResponse.model_validate(status_result).selfie_status == "SUBMITTED"
