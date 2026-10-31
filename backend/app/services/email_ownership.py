from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_ownership_challenge import EmailOwnershipChallenge
from app.models.user import User, normalize_email
from app.services.email import EmailDeliveryUnavailable, EmailSender


EMAIL_CODE_TTL = timedelta(minutes=10)
EMAIL_CODE_RESEND_COOLDOWN = timedelta(minutes=1)
MAX_EMAIL_CODE_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _code_hash(challenge_id: uuid.UUID, code: str) -> str:
    key = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    value = f"{challenge_id}:{code}".encode("utf-8")
    return hmac.new(key, value, hashlib.sha256).hexdigest()


def _latest_challenge(
    db: Session,
    user_id: uuid.UUID,
    for_update: bool = False,
) -> EmailOwnershipChallenge | None:
    query = (
        select(EmailOwnershipChallenge)
        .where(EmailOwnershipChallenge.user_id == user_id)
        .order_by(EmailOwnershipChallenge.created_at.desc())
        .limit(1)
    )
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)


def email_ownership_status(db: Session, user: User) -> dict:
    latest = _latest_challenge(db, user.id)
    has_pending_change = (
        latest is not None
        and latest.consumed_at is None
        and latest.email != user.verified_email
    )
    if user.verified_email and user.email_verified_at and not has_pending_change:
        current_status = "VERIFIED"
    elif latest is None:
        current_status = "NOT_VERIFIED"
    elif latest.attempt_count >= MAX_EMAIL_CODE_ATTEMPTS:
        current_status = "INVALID_CODE"
    elif _aware(latest.expires_at) <= _now():
        current_status = "CODE_EXPIRED"
    elif latest.consumed_at is None:
        current_status = "INVALID_CODE" if latest.attempt_count else "CODE_SENT"
    else:
        current_status = "INVALID_CODE"

    resend_available_at = None
    if latest is not None:
        resend_available_at = _aware(latest.created_at) + EMAIL_CODE_RESEND_COOLDOWN
    pending = latest is not None and latest.consumed_at is None
    return {
        "status": current_status,
        "email": latest.email if pending else user.verified_email or user.email,
        "verified_email": user.verified_email,
        "expires_at": latest.expires_at if pending else None,
        "resend_available_at": resend_available_at,
    }


def send_email_ownership_code(db: Session, user: User, email: str, sender: EmailSender) -> dict:
    normalized_email = normalize_email(email)
    now = _now()
    if normalized_email == user.verified_email and user.email_verified_at is not None:
        return {
            "status": "VERIFIED",
            "email": normalized_email,
            "verified_email": user.verified_email,
            "expires_at": None,
            "resend_available_at": None,
        }
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    latest = _latest_challenge(db, user.id)
    if latest is not None and now - _aware(latest.created_at) < EMAIL_CODE_RESEND_COOLDOWN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another verification code",
        )
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailOwnershipChallenge(
        id=uuid.uuid4(),
        user_id=user.id,
        email=normalized_email,
        code_hash="",
        expires_at=now + EMAIL_CODE_TTL,
    )
    challenge.code_hash = _code_hash(challenge.id, code)
    if latest is not None and latest.consumed_at is None:
        latest.consumed_at = now
    db.add(challenge)
    try:
        db.flush()
        sender.send_email_ownership_code(normalized_email, code, challenge.expires_at)
        db.commit()
    except EmailDeliveryUnavailable:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is not available",
        ) from None

    return {
        "status": "CODE_SENT",
        "email": normalized_email,
        "verified_email": user.verified_email,
        "expires_at": challenge.expires_at,
        "resend_available_at": now + EMAIL_CODE_RESEND_COOLDOWN,
    }


def confirm_email_ownership_code(db: Session, user: User, code: str) -> dict:
    challenge = _latest_challenge(db, user.id, for_update=True)
    now = _now()
    if challenge is None or challenge.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
    if _aware(challenge.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Verification code has expired")
    if challenge.attempt_count >= MAX_EMAIL_CODE_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")

    if not hmac.compare_digest(challenge.code_hash, _code_hash(challenge.id, code)):
        challenge.attempt_count += 1
        db.commit()
        if challenge.attempt_count >= MAX_EMAIL_CODE_ATTEMPTS:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    challenge.consumed_at = now
    user.verified_email = challenge.email
    user.email_verified_at = now
    db.commit()
    return {
        "status": "VERIFIED",
        "email": challenge.email,
        "verified_email": user.verified_email,
        "expires_at": None,
        "resend_available_at": None,
    }
