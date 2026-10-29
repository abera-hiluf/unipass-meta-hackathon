import enum


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


VERIFICATION_STATUSES = tuple(status.value for status in VerificationStatus)
