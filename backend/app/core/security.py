import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt

from app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using the Argon2 password hashing algorithm."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns False if verification fails or the hash format is invalid.
    """
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: str,
    role: str = "student",
    expires_delta: timedelta | None = None,
    additional_claims: dict | None = None,
) -> str:
    """Create a signed JWT access token with subject, role, issue time, and expiration."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Validates signature, expiration, and algorithm. Raises jwt.PyJWTError on invalid token.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


def normalize_document_identifier(document_id: str) -> str:
    """Normalize a document identifier by removing whitespace, hyphens, and converting to uppercase.

    Example: "  a-123 456 78  " -> "A12345678"
    """
    return re.sub(r"[\s\-]", "", document_id).upper()


def compute_document_fingerprint(document_id: str, secret: str | None = None) -> str:
    """Compute a keyed HMAC-SHA256 fingerprint for a normalized document identifier.

    Uses a secret key outside the database (loaded from secure environment configuration)
    so the raw document number cannot be reverse-engineered or subjected to offline
    dictionary attacks.
    """
    key = secret if secret is not None else settings.document_hmac_secret
    normalized = normalize_document_identifier(document_id)
    return hmac.new(key.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()
