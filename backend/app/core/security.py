import hashlib
import hmac
import re

from app.core.config import settings


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
