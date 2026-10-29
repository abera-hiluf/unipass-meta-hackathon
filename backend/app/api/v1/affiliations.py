import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.eligibility import EligibilityVerificationRequest, EligibilityVerificationResponse
from app.schemas.institutions import AffiliationResponse
from app.services.eligibility import EligibilityAdapter, get_eligibility_adapter, verify_affiliation_eligibility
from app.services.institutions import list_user_affiliations


router = APIRouter(prefix="/affiliations", tags=["Affiliations"])


@router.post(
    "/{affiliation_id}/verify-eligibility",
    response_model=EligibilityVerificationResponse,
    status_code=status.HTTP_200_OK,
)
def verify_eligibility(
    affiliation_id: uuid.UUID,
    payload: EligibilityVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter: EligibilityAdapter = Depends(get_eligibility_adapter),
) -> EligibilityVerificationResponse:
    result = verify_affiliation_eligibility(
        db=db,
        user=current_user,
        affiliation_id=affiliation_id,
        student_identifier=payload.student_identifier,
        adapter=adapter,
    )
    return EligibilityVerificationResponse(
        status="enrollment_confirmed" if result.outcome == "confirmed" else "enrollment_rejected" if result.outcome == "rejected" else "enrollment_pending",
        outcome=result.outcome,
        reason_code=result.reason_code,
        source=result.source,
    )


@router.get("/me", response_model=list[AffiliationResponse])
def get_my_affiliations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AffiliationResponse]:
    affiliations = list_user_affiliations(db, current_user.id)
    return [
        AffiliationResponse(
            id=affiliation.id,
            institution_id=affiliation.institution_id,
            institution_name=affiliation.institution.official_display_name,
            institutional_email=affiliation.institutional_email,
            status=affiliation.status,
            email_verified_at=affiliation.email_verified_at,
            eligibility_source=affiliation.eligibility_source,
            eligibility_checked_at=affiliation.eligibility_checked_at,
            eligibility_reason_code=affiliation.eligibility_reason_code,
        )
        for affiliation in affiliations
    ]
