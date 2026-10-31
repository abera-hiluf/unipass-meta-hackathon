from __future__ import annotations

from email.message import EmailMessage
import smtplib
import ssl
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

    def send_email_ownership_code(
        self,
        recipient: str,
        code: str,
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

    def send_email_ownership_code(
        self,
        recipient: str,
        code: str,
        expires_at: datetime,
    ) -> None:
        raise EmailDeliveryUnavailable("No email provider is configured")


class SMTPEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None,
        password: str | None,
        starttls: bool,
        use_ssl: bool,
        timeout_seconds: float,
    ) -> None:
        self.host = host
        self.port = port
        self.sender = sender
        self.username = username
        self.password = password
        self.starttls = starttls
        self.use_ssl = use_ssl
        self.timeout_seconds = timeout_seconds

    def _send(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout_seconds,
                    context=ssl.create_default_context(),
                ) as client:
                    self._deliver(client, message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as client:
                    if self.starttls:
                        client.starttls(context=ssl.create_default_context())
                    self._deliver(client, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryUnavailable("SMTP email delivery failed") from exc

    def _deliver(self, client: smtplib.SMTP, message: EmailMessage) -> None:
        if self.username:
            client.login(self.username, self.password or "")
        client.send_message(message)

    def send_verification_email(
        self,
        recipient: str,
        institution_name: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        self._send(
            recipient,
            f"Verify your {institution_name} email",
            f"Use this one-time verification token: {token}\n"
            f"It expires at {expires_at.isoformat()}.",
        )

    def send_email_ownership_code(
        self,
        recipient: str,
        code: str,
        expires_at: datetime,
    ) -> None:
        self._send(
            recipient,
            "UniPass email verification code",
            f"Your UniPass email verification code is {code}.\n"
            f"It expires at {expires_at.isoformat()}. Do not share this code.",
        )


def get_email_sender() -> EmailSender:
    if (
        settings.email_provider.lower() != "smtp"
        or not settings.smtp_host
        or not settings.smtp_sender
    ):
        return UnconfiguredEmailSender()
    return SMTPEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_sender,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
        starttls=settings.smtp_starttls,
        use_ssl=settings.smtp_ssl,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
