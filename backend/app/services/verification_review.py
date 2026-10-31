from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.identity_verification import IdentityVerification
from app.models.institution_affiliation import InstitutionAffiliation
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def require_reviewer(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authorized reviewer access required")


def _affiliation_statuses(db: Session, user_id: uuid.UUID) -> list[str]:
    return [status_value for (status_value,) in db.query(InstitutionAffiliation.status).filter(InstitutionAffiliation.user_id == user_id).all()]


def identity_status(db: Session, user: User) -> dict:
    verification = (
        db.query(IdentityVerification)
        .filter(IdentityVerification.user_id == user.id)
        .order_by(IdentityVerification.created_at.desc())
        .first()
    )
    affiliations = _affiliation_statuses(db, user.id)
    if verification is None:
        return {
            "verification_id": None,
            "outcome": "PENDING",
            "verification_status": None,
            "affiliation_statuses": affiliations,
            "liveness_status": None,
            "selfie_status": None,
            "face_match_status": None,
            "document_analysis_status": None,
        }
    outcome = {
        "APPROVED": "VERIFIED",
        "REJECTED": "REJECTED",
        "FLAGGED": "REVIEW_REQUIRED",
        "FAILED": "FAILED",
    }.get(verification.status, "PENDING")
    return {
        "verification_id": verification.id,
        "outcome": outcome,
        "verification_status": verification.status,
        "affiliation_statuses": affiliations,
        "liveness_status": verification.liveness_status,
        "selfie_status": verification.selfie_status,
        "face_match_status": verification.face_match_status,
        "document_analysis_status": verification.status if verification.analysis_completed_at else None,
    }


def list_review_cases(db: Session, reviewer: User) -> list[dict]:
    require_reviewer(reviewer)
    cases = (
        db.query(IdentityVerification)
        .filter(IdentityVerification.status.in_(["COMPLETED", "FLAGGED", "PENDING", "RETRY_REQUIRED"]))
        .order_by(IdentityVerification.created_at.asc())
        .all()
    )
    return [
        {
            "verification_id": case.id,
            "status": case.status,
            "liveness_status": case.liveness_status,
            "face_match_status": case.face_match_status,
            "analysis_status": case.status if case.analysis_completed_at else "NOT_STARTED",
        }
        for case in cases
    ]


def review_case(db: Session, reviewer: User, verification_id: uuid.UUID, decision: str, reason: str) -> dict:
    require_reviewer(reviewer)
    case = db.get(IdentityVerification, verification_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    decision = decision.lower()
    if decision == "approve":
        confirmed = db.query(InstitutionAffiliation).filter(
            InstitutionAffiliation.user_id == case.user_id,
            InstitutionAffiliation.status == "enrollment_confirmed",
        ).first()
        if confirmed is None or case.status not in {"COMPLETED", "FLAGGED"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Verification evidence is not ready for approval")
        if case.liveness_status != "LIVE" or case.face_match_status != "MATCH":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Liveness and face-match evidence require successful configured providers")
        case.transition_to("APPROVED")
        outcome = "VERIFIED"
    elif decision == "reject":
        if case.status != "REJECTED":
            case.transition_to("REJECTED")
        outcome = "REJECTED"
    elif decision == "resubmit":
        if case.status in {"COMPLETED", "PENDING", "RETRY_REQUIRED"}:
            case.transition_to("FLAGGED")
        outcome = "REVIEW_REQUIRED"
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported review decision")

    reviewed_at = _now()
    case.reviewed_by = reviewer.id
    case.reviewed_at = reviewed_at
    case.review_notes = reason
    db.add(AuditLog(
        actor_user_id=reviewer.id,
        action="IDENTITY_VERIFICATION_REVIEWED",
        resource_type="identity_verification",
        resource_id=str(case.id),
        details={"decision": decision, "outcome": outcome},
    ))
    db.commit()
    return {
        "verification_id": case.id,
        "outcome": outcome,
        "status": case.status,
        "reason": reason,
        "reviewed_at": reviewed_at,
    }
