from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.core.config import settings


class EmailDeliveryUnavailable(RuntimeError):
    """Raised when no configured provider can deliver an email."""


class EmailSender(Protocol):
    def send_verification_email(
        self,
        recipient: str,
        institution_name: str,
        token: str,
        expires_at: datetime,
    ) -> None: ...


class UnconfiguredEmailSender:
    def send_verification_email(
        self,
        recipient: str,
        institution_name: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        raise EmailDeliveryUnavailable("No email provider is configured")


def get_email_sender() -> EmailSender:
    # Test code can override this dependency with a mock sender. Production
    # never claims delivery while no provider integration is configured.
    if settings.email_provider.lower() == "none":
        return UnconfiguredEmailSender()
    return UnconfiguredEmailSender()
