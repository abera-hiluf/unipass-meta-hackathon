from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import user as user_repo
from app.schemas.auth import UserLoginRequest, UserRegisterRequest


def register_user(db: Session, data: UserRegisterRequest) -> User:
    """Register a new user after checking for duplicate email."""
    existing_user = user_repo.get_user_by_email(db, data.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    hashed_pw = hash_password(data.password)
    try:
        user = user_repo.create_user(
            db=db,
            email=data.email,
            hashed_password=hashed_pw,
            role=data.role,
        )
    except IntegrityError:
        # The pre-check handles normal duplicates; this handles concurrent requests
        # that race to insert the same unique email.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    return user


def authenticate_user(db: Session, data: UserLoginRequest) -> str:
    """Authenticate credentials and generate a JWT access token.

    Uses generic failure message to avoid username enumeration.
    """
    user = user_repo.get_user_by_email(db, data.email)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role,
    )
    return access_token
