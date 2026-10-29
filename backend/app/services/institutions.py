from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerificationChallenge
from app.models.institution import Institution, InstitutionEmailDomain
from app.models.institution_affiliation import InstitutionAffiliation
from app.models.user import User, normalize_email
from app.services.email import EmailDeliveryUnavailable, EmailSender


VERIFICATION_TOKEN_TTL = timedelta(minutes=15)
VERIFICATION_ISSUANCE_COOLDOWN = timedelta(minutes=1)
MAX_VERIFICATION_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def list_active_institutions(db: Session) -> list[Institution]:
    return list(
        db.scalars(
            select(Institution).where(Institution.is_active.is_(True)).order_by(Institution.official_display_name)
        ).all()
    )


def list_user_affiliations(db: Session, user_id: uuid.UUID) -> list[InstitutionAffiliation]:
    return list(
        db.scalars(
            select(InstitutionAffiliation)
            .where(InstitutionAffiliation.user_id == user_id)
            .order_by(InstitutionAffiliation.created_at)
        ).all()
    )


def request_email_verification(
    db: Session,
    user: User,
    institution_id: uuid.UUID,
    institutional_email: str,
    sender: EmailSender,
) -> None:
    now = _now()
    email = normalize_email(institutional_email)
    domain = email.rsplit("@", 1)[-1]

    institution = db.scalar(
        select(Institution).where(Institution.id == institution_id, Institution.is_active.is_(True))
    )
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    trusted_domain = db.scalar(
        select(InstitutionEmailDomain).where(
            InstitutionEmailDomain.institution_id == institution_id,
            InstitutionEmailDomain.domain == domain,
            InstitutionEmailDomain.is_verified.is_(True),
        )
    )
    if trusted_domain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is not configured for this institution",
        )

    affiliation = db.scalar(
        select(InstitutionAffiliation).where(
            InstitutionAffiliation.user_id == user.id,
            InstitutionAffiliation.institution_id == institution_id,
        )
    )
    if affiliation is None:
        affiliation = InstitutionAffiliation(
            user_id=user.id,
            institution_id=institution_id,
            institutional_email=email,
        )
        db.add(affiliation)
        db.flush()
    elif affiliation.status == "enrollment_confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to start email verification")
    elif affiliation.institutional_email != email:
        affiliation.institutional_email = email
        affiliation.status = "email_not_verified"
        affiliation.email_verified_at = None

    latest = db.scalar(
        select(EmailVerificationChallenge)
        .where(
            EmailVerificationChallenge.affiliation_id == affiliation.id,
            EmailVerificationChallenge.consumed_at.is_(None),
        )
        .order_by(EmailVerificationChallenge.created_at.desc())
    )
    if latest is not None:
        created_at = _as_aware(latest.created_at)
        if latest.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")
        if now - created_at < VERIFICATION_ISSUANCE_COOLDOWN:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Please wait before requesting another verification email")
        latest.consumed_at = now

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + VERIFICATION_TOKEN_TTL
    challenge = EmailVerificationChallenge(
        affiliation_id=affiliation.id,
        token_hash=hash_verification_token(raw_token),
        expires_at=expires_at,
    )
    db.add(challenge)
    try:
        db.flush()
        sender.send_verification_email(email, institution.official_display_name, raw_token, expires_at)
        db.commit()
    except EmailDeliveryUnavailable:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is not available",
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to start email verification",
        ) from None


def confirm_email_verification(db: Session, user: User, token: str) -> None:
    now = _now()
    token_hash = hash_verification_token(token)
    challenge = db.scalar(
        select(EmailVerificationChallenge)
        .join(InstitutionAffiliation, InstitutionAffiliation.id == EmailVerificationChallenge.affiliation_id)
        .where(
            InstitutionAffiliation.user_id == user.id,
            EmailVerificationChallenge.token_hash == token_hash,
            EmailVerificationChallenge.consumed_at.is_(None),
        )
    )

    if challenge is None:
        latest = db.scalar(
            select(EmailVerificationChallenge)
            .join(InstitutionAffiliation, InstitutionAffiliation.id == EmailVerificationChallenge.affiliation_id)
            .where(
                InstitutionAffiliation.user_id == user.id,
                EmailVerificationChallenge.consumed_at.is_(None),
            )
            .order_by(EmailVerificationChallenge.created_at.desc())
        )
        if latest is not None and _as_aware(latest.expires_at) > now:
            latest.attempt_count += 1
            db.commit()
            if latest.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")

    if challenge.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")
    if _as_aware(challenge.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")

    challenge.consumed_at = now
    affiliation = challenge.affiliation
    affiliation.status = "email_verified"
    affiliation.email_verified_at = now
    db.commit()
