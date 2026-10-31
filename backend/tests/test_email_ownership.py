from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import get_email_sender
from app.db import Base, get_db
from app.main import app
from app.models.email_ownership_challenge import EmailOwnershipChallenge
from app.models.institution import Institution
from app.models.institution_affiliation import InstitutionAffiliation
from app.models.user import User
from app.services.email import EmailDeliveryUnavailable, SMTPEmailSender, UnconfiguredEmailSender


class MockEmailSender:
    def __init__(self, fail: bool = False) -> None:
        self.codes: list[tuple[str, str]] = []
        self.fail = fail

    def send_verification_email(self, recipient, institution_name, token, expires_at) -> None:
        return None

    def send_email_ownership_code(self, recipient, code, expires_at) -> None:
        if self.fail:
            raise EmailDeliveryUnavailable("synthetic delivery failure")
        self.codes.append((recipient, code))


@pytest.fixture
def email_context():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sender = MockEmailSender()
    with SessionLocal() as db:
        db.add(Institution(
            slug="email-test-university",
            official_display_name="Email Test University",
            is_active=True,
            is_development_only=True,
        ))
        db.commit()
        institution_id = db.query(Institution).one().id

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: sender
    with TestClient(app) as client:
        yield client, SessionLocal, sender, institution_id
    app.dependency_overrides.clear()
    engine.dispose()


def register_and_login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecureEmailPassword2026!"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureEmailPassword2026!"},
    )
    assert login.status_code == status.HTTP_200_OK
    return login.json()["access_token"]


def test_email_ownership_code_is_sent_confirmed_and_single_use(email_context) -> None:
    client, SessionLocal, sender, _ = email_context
    token = register_and_login(client, "account@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    issued = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": " Student@Gmail.com "},
    )
    assert issued.status_code == status.HTTP_202_ACCEPTED
    assert issued.json()["status"] == "CODE_SENT"
    assert "code" not in issued.json()
    assert sender.codes[-1][0] == "student@gmail.com"
    code = sender.codes[-1][1]

    wrong_code = "000000" if code != "000000" else "000001"
    invalid = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers=headers,
        json={"code": wrong_code},
    )
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST

    confirmed = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers=headers,
        json={"code": code},
    )
    assert confirmed.status_code == status.HTTP_200_OK
    assert confirmed.json()["status"] == "VERIFIED"
    assert confirmed.json()["verified_email"] == "student@gmail.com"
    reused = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers=headers,
        json={"code": code},
    )
    assert reused.status_code == status.HTTP_400_BAD_REQUEST

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "account@example.com").one()
        challenge = db.query(EmailOwnershipChallenge).one()
        assert user.verified_email == "student@gmail.com"
        assert user.email_verified_at is not None
        assert challenge.consumed_at is not None
        assert challenge.code_hash != code


def test_email_ownership_expiration_attempts_and_resend_cooldown(email_context) -> None:
    client, SessionLocal, sender, _ = email_context
    token = register_and_login(client, "expiry@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    issued = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": "expiry@gmail.com"},
    )
    assert issued.status_code == status.HTTP_202_ACCEPTED

    too_soon = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": "expiry@gmail.com"},
    )
    assert too_soon.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    code = sender.codes[-1][1]
    invalid_code = "000000" if code != "000000" else "000001"
    invalid = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers=headers,
        json={"code": invalid_code},
    )
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST

    with SessionLocal() as db:
        challenge = db.query(EmailOwnershipChallenge).one()
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        challenge.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        db.commit()

    expired = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers=headers,
        json={"code": code},
    )
    assert expired.status_code == status.HTTP_410_GONE
    current = client.get("/api/v1/auth/email-verification", headers=headers)
    assert current.json()["status"] == "CODE_EXPIRED"

    resent = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": "expiry@gmail.com"},
    )
    assert resent.status_code == status.HTTP_202_ACCEPTED
    assert resent.json()["status"] == "CODE_SENT"


def test_email_delivery_failure_does_not_create_challenge(email_context) -> None:
    client, SessionLocal, _, _ = email_context
    token = register_and_login(client, "delivery-failure@example.com")
    app.dependency_overrides[get_email_sender] = lambda: UnconfiguredEmailSender()

    response = client.post(
        "/api/v1/auth/email-verification/code",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "delivery@gmail.com"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    with SessionLocal() as db:
        assert db.query(EmailOwnershipChallenge).count() == 0


def test_email_code_attempt_limit_allows_a_cooldown_resend(email_context) -> None:
    client, SessionLocal, sender, _ = email_context
    token = register_and_login(client, "attempt-limit@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    issued = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": "attempt-limit@gmail.com"},
    )
    assert issued.status_code == status.HTTP_202_ACCEPTED
    correct_code = sender.codes[-1][1]
    invalid_code = "000000" if correct_code != "000000" else "000001"

    responses = [
        client.post(
            "/api/v1/auth/email-verification/confirm",
            headers=headers,
            json={"code": invalid_code},
        )
        for _ in range(5)
    ]
    assert [response.status_code for response in responses] == [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_429_TOO_MANY_REQUESTS,
    ]
    assert client.get("/api/v1/auth/email-verification", headers=headers).json()["status"] == "INVALID_CODE"

    with SessionLocal() as db:
        challenge = db.query(EmailOwnershipChallenge).one()
        challenge.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        db.commit()
    resent = client.post(
        "/api/v1/auth/email-verification/code",
        headers=headers,
        json={"email": "attempt-limit@gmail.com"},
    )
    assert resent.status_code == status.HTTP_202_ACCEPTED
    assert sender.codes[-1][1] != correct_code


def test_smtp_sender_delivers_code_using_configured_transport(monkeypatch) -> None:
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured["host"] = host
            captured["port"] = port
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, context):
            captured["starttls"] = context is not None

        def login(self, username, password):
            captured["credentials"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    sender = SMTPEmailSender(
        host="smtp.example.test",
        port=587,
        sender="verify@example.test",
        username="smtp-user",
        password="smtp-password",
        starttls=True,
        use_ssl=False,
        timeout_seconds=5,
    )
    sender.send_email_ownership_code(
        "student@gmail.com",
        "123456",
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    assert captured["host"] == "smtp.example.test"
    assert captured["timeout"] == 5
    assert captured["starttls"] is True
    assert captured["credentials"] == ("smtp-user", "smtp-password")
    assert captured["message"]["To"] == "student@gmail.com"
    assert "123456" in captured["message"].get_content()


def test_email_code_cannot_be_confirmed_by_another_user(email_context) -> None:
    client, _, sender, _ = email_context
    owner_token = register_and_login(client, "code-owner@example.com")
    other_token = register_and_login(client, "code-other@example.com")
    issued = client.post(
        "/api/v1/auth/email-verification/code",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "owner@gmail.com"},
    )
    assert issued.status_code == status.HTTP_202_ACCEPTED

    rejected = client.post(
        "/api/v1/auth/email-verification/confirm",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"code": sender.codes[-1][1]},
    )
    assert rejected.status_code == status.HTTP_400_BAD_REQUEST


def test_institution_selection_persists_without_creating_enrollment(email_context) -> None:
    client, SessionLocal, _, institution_id = email_context
    token = register_and_login(client, "selection@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    saved = client.post(
        "/api/v1/institutions/me/selection",
        headers=headers,
        json={"institution_id": str(institution_id)},
    )
    assert saved.status_code == status.HTTP_200_OK
    assert saved.json()["institution_id"] == str(institution_id)
    assert saved.json()["enrollment_status"] == "NOT_VERIFIED"
    read_back = client.get("/api/v1/institutions/me/selection", headers=headers)
    assert read_back.json()["institution_name"] == "Email Test University"

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "selection@example.com").one()
        assert user.selected_institution_id == institution_id
        assert db.query(InstitutionAffiliation).count() == 0
