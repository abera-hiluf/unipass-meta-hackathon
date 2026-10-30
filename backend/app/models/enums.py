import enum


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    FAILED = "FAILED"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


VERIFICATION_STATUSES = tuple(status.value for status in VerificationStatus)
