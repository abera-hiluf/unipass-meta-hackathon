from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_identity_demo_enabled
from app.db import get_db
from app.models.user import User, normalize_email
from app.schemas.auth import (
    DemoContactEmailRequest,
    DemoContactEmailResponse,
    EmailOwnershipCodeRequest,
    EmailOwnershipConfirmRequest,
    EmailOwnershipStatusResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.email import EmailSender, get_email_sender
from app.services.email_ownership import (
    confirm_email_ownership_code,
    email_ownership_status,
    send_email_ownership_code,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    """Register a new student or admin account with normalized email and Argon2 password hashing.

    Note: Account creation does NOT grant verified student identity or campus service access.
    """
    user = auth_service.register_user(db=db, data=payload)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT access token",
)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verify credentials with Argon2 and return a scoped JWT access token."""
    token = auth_service.authenticate_user(db=db, data=payload)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current authenticated user account",
)
def get_current_account(
    current_user: User = Depends(get_current_user),
) -> User:
    """Retrieve safe account details for the authenticated bearer token holder."""
    return current_user


@router.get("/email-verification", response_model=EmailOwnershipStatusResponse)
def get_email_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _email_status_response(db, current_user)


@router.get("/demo-contact-email", response_model=DemoContactEmailResponse)
def get_demo_contact_email(
    current_user: User = Depends(get_current_user),
) -> dict[str, str | bool | None]:
    if not is_identity_demo_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo contact email is available only in local identity demo mode",
        )
    return {"identity_demo_mode": True, "email": current_user.demo_email}


@router.put("/demo-contact-email", response_model=DemoContactEmailResponse)
def save_demo_contact_email(
    payload: DemoContactEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | bool | None]:
    if not is_identity_demo_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo contact email is available only in local identity demo mode",
        )
    current_user.demo_email = normalize_email(str(payload.email))
    current_user.demo_email_confirmed_at = None
    db.commit()
    return {"identity_demo_mode": True, "email": current_user.demo_email}


@router.post("/email-verification/code", response_model=EmailOwnershipStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def issue_email_verification_code(
    payload: EmailOwnershipCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
) -> dict:
    if is_identity_demo_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email verification codes are disabled in local identity demo mode",
        )
    response = send_email_ownership_code(db, current_user, str(payload.email), sender)
    return _email_status_response(db, current_user, response)


@router.post("/email-verification/confirm", response_model=EmailOwnershipStatusResponse)
def confirm_email_verification_code(
    payload: EmailOwnershipConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if is_identity_demo_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email verification codes are disabled in local identity demo mode",
        )
    response = confirm_email_ownership_code(db, current_user, payload.code)
    return _email_status_response(db, current_user, response)


def _email_status_response(db: Session, user: User, response: dict | None = None) -> dict:
    return response or email_ownership_status(db, user)
