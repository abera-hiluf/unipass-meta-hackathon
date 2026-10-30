from app.models.audit_log import AuditLog
from app.models.enums import VERIFICATION_STATUSES, VerificationStatus
from app.models.identity_verification import FACE_MATCH_STATUSES, IdentityVerification, LIVENESS_STATUSES, SELFIE_STATUSES, VALID_IDENTITY_VERIFICATION_TRANSITIONS
from app.models.email_verification import EmailVerificationChallenge
from app.models.institution import Institution, InstitutionEmailDomain
from app.models.institution_affiliation import (
    AFFILIATION_STATUSES,
    InstitutionAffiliation,
    VALID_AFFILIATION_TRANSITIONS,
)
from app.models.student_profile import StudentProfile
from app.models.user import User, normalize_email

__all__ = [
    "AuditLog",
    "IdentityVerification",
    "VALID_IDENTITY_VERIFICATION_TRANSITIONS",
    "SELFIE_STATUSES",
    "Institution",
    "InstitutionEmailDomain",
    "InstitutionAffiliation",
    "AFFILIATION_STATUSES",
    "VALID_AFFILIATION_TRANSITIONS",
    "EmailVerificationChallenge",
    "StudentProfile",
    "User",
    "VerificationStatus",
    "VERIFICATION_STATUSES",
    "normalize_email",
]
