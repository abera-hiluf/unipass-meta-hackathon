from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.institution import Institution
from app.models.institution_affiliation import InstitutionAffiliation
from app.models.user import User


@dataclass(frozen=True)
class EligibilityResult:
    outcome: str
    reason_code: str
    source: str
    development_only: bool


class EligibilityAdapter(Protocol):
    def verify(self, institution: Institution, student_identifier: str) -> EligibilityResult: ...


class UnavailableEligibilityAdapter:
    def verify(self, institution: Institution, student_identifier: str) -> EligibilityResult:
        return EligibilityResult(
            outcome="inconclusive",
            reason_code="source_unavailable",
            source="unavailable",
            development_only=False,
        )


class MockEligibilityAdapter:
    """Development-only adapter backed by explicitly supplied synthetic records."""

    development_only = True

    def __init__(self, records: set[tuple[str, str]]) -> None:
        self.records = records

    def verify(self, institution: Institution, student_identifier: str) -> EligibilityResult:
        if (institution.slug, student_identifier) in self.records:
            return EligibilityResult(
                outcome="confirmed",
                reason_code="synthetic_record_match",
                source="mock_development",
                development_only=True,
            )
        return EligibilityResult(
            outcome="rejected",
            reason_code="synthetic_record_not_found",
            source="mock_development",
            development_only=True,
        )


def get_eligibility_adapter() -> EligibilityAdapter:
    # No authorized roster, API, or SSO provider is configured. Tests may
    # override this dependency with MockEligibilityAdapter.
    return UnavailableEligibilityAdapter()


def verify_affiliation_eligibility(
    db: Session,
    user: User,
    affiliation_id: uuid.UUID,
    student_identifier: str,
    adapter: EligibilityAdapter,
) -> EligibilityResult:
    affiliation = db.scalar(
        select(InstitutionAffiliation)
        .join(Institution, Institution.id == InstitutionAffiliation.institution_id)
        .where(InstitutionAffiliation.id == affiliation_id, InstitutionAffiliation.user_id == user.id)
    )
    if affiliation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affiliation not found")
    if not affiliation.institution.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Institution is inactive")
    if affiliation.status not in {
        "email_verified",
        "enrollment_pending",
        "enrollment_rejected",
        "enrollment_revoked",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Institutional email must be verified before eligibility can be checked",
        )

    try:
        if affiliation.status != "enrollment_pending":
            affiliation.transition_to("enrollment_pending")
        result = adapter.verify(affiliation.institution, student_identifier)
        if result.outcome == "confirmed" and (
            not settings.environment.lower().startswith("development") or not result.development_only
        ):
            result = EligibilityResult(
                outcome="inconclusive",
                reason_code="authoritative_source_not_configured",
                source=result.source,
                development_only=result.development_only,
            )

        affiliation.eligibility_source = result.source
        affiliation.eligibility_reason_code = result.reason_code
        affiliation.eligibility_checked_at = datetime.now(timezone.utc)
        if result.outcome == "confirmed":
            affiliation.transition_to("enrollment_confirmed")
        elif result.outcome == "rejected":
            affiliation.transition_to("enrollment_rejected")
        db.commit()
        return result
    except ValueError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid affiliation status transition") from None
