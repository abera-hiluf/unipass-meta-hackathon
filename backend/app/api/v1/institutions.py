import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.institution_affiliation import InstitutionAffiliation
from app.models.user import User
from app.schemas.institutions import (
    AffiliationResponse,
    EmailVerificationConfirmRequest,
    EmailVerificationResponse,
    InstitutionEmailVerificationRequest,
    InstitutionResponse,
)
from app.services.email import EmailSender, get_email_sender
from app.services.institutions import (
    confirm_email_verification,
    list_active_institutions,
    list_user_affiliations,
    request_email_verification,
)


router = APIRouter(prefix="/institutions", tags=["Institutions"])


@router.get("", response_model=list[InstitutionResponse])
def list_institutions(db: Session = Depends(get_db)) -> list:
    return list_active_institutions(db)


@router.post(
    "/{institution_id}/email-verification",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def issue_email_verification(
    institution_id: uuid.UUID,
    payload: InstitutionEmailVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
) -> EmailVerificationResponse:
    request_email_verification(
        db=db,
        user=current_user,
        institution_id=institution_id,
        institutional_email=str(payload.institutional_email),
        sender=sender,
    )
    return EmailVerificationResponse(detail="Verification email dispatched")


@router.post(
    "/email-verification/confirm",
    response_model=EmailVerificationResponse,
)
def confirm_email_verification_route(
    payload: EmailVerificationConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailVerificationResponse:
    confirm_email_verification(db=db, user=current_user, token=payload.token)
    return EmailVerificationResponse(detail="Institutional email verified")


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
