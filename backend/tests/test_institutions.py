from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.institutions import get_email_sender
from app.db import Base, get_db
from app.main import app
from app.models.email_verification import EmailVerificationChallenge
from app.models.institution import Institution, InstitutionEmailDomain
from app.models.institution_affiliation import InstitutionAffiliation
from app.services.institutions import hash_verification_token


class MockEmailSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_verification_email(self, recipient, institution_name, token, expires_at) -> None:
        self.messages.append({"recipient": recipient, "institution_name": institution_name, "token": token})


@pytest.fixture
def institution_test_context():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sender = MockEmailSender()

    with SessionLocal() as setup_db:
        institution = Institution(
            slug="verified-test-university",
            official_display_name="Verified Test University",
            is_active=True,
            is_development_only=True,
        )
        institution.email_domains.append(
            InstitutionEmailDomain(domain="students.test.edu", is_verified=True, verification_source="synthetic test")
        )
        pilot = Institution(
            slug="anna-university-bit-campus-development",
            official_display_name="Anna University, BIT Campus, Tiruchirappalli",
            is_active=True,
            is_development_only=True,
        )
        setup_db.add_all([institution, pilot])
        setup_db.commit()
        institution_id = institution.id
        pilot_id = pilot.id

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: sender
    with TestClient(app) as client:
        yield client, SessionLocal, sender, institution_id, pilot_id
    app.dependency_overrides.clear()
    engine.dispose()


def register_and_login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecureTestPassword2026!"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureTestPassword2026!"},
    )
    assert login.status_code == status.HTTP_200_OK
    return login.json()["access_token"]


def test_lists_active_institutions_without_trusting_domains(institution_test_context) -> None:
    client, _, _, _, pilot_id = institution_test_context
    response = client.get("/api/v1/institutions")

    assert response.status_code == status.HTTP_200_OK
    pilot = next(item for item in response.json() if item["id"] == str(pilot_id))
    assert pilot["is_development_only"] is True
    assert "email_domains" not in pilot


def test_invalid_institution_is_rejected(institution_test_context) -> None:
    client, _, _, _, _ = institution_test_context
    token = register_and_login(client, "invalid-institution@example.com")
    response = client.post(
        f"/api/v1/institutions/{uuid.uuid4()}/email-verification",
        headers={"Authorization": f"Bearer {token}"},
        json={"institutional_email": "student@students.test.edu"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_untrusted_pilot_domain_does_not_verify(institution_test_context) -> None:
    client, _, _, _, pilot_id = institution_test_context
    token = register_and_login(client, "pilot@example.com")
    response = client.post(
        f"/api/v1/institutions/{pilot_id}/email-verification",
        headers={"Authorization": f"Bearer {token}"},
        json={"institutional_email": "student@any-domain.example"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_email_verification_success_and_token_reuse_is_blocked(institution_test_context) -> None:
    client, SessionLocal, sender, institution_id, _ = institution_test_context
    token = register_and_login(client, "student@example.com")
    issue = client.post(
        f"/api/v1/institutions/{institution_id}/email-verification",
        headers={"Authorization": f"Bearer {token}"},
        json={"institutional_email": " Student@Students.Test.edu "},
    )
    assert issue.status_code == status.HTTP_202_ACCEPTED
    assert "token" not in issue.json()
    verification_token = sender.messages[-1]["token"]

    confirm = client.post(
        "/api/v1/institutions/email-verification/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"token": verification_token},
    )
    assert confirm.status_code == status.HTTP_200_OK

    reused = client.post(
        "/api/v1/institutions/email-verification/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"token": verification_token},
    )
    assert reused.status_code == status.HTTP_400_BAD_REQUEST

    with SessionLocal() as db:
        affiliation = db.query(InstitutionAffiliation).one()
        assert affiliation.status == "email_verified"
        assert db.query(EmailVerificationChallenge).one().token_hash == hash_verification_token(verification_token)


def test_expired_token_and_wrong_owner_are_rejected(institution_test_context) -> None:
    client, SessionLocal, sender, institution_id, _ = institution_test_context
    owner_token = register_and_login(client, "owner@example.com")
    other_user_token = register_and_login(client, "other@example.com")
    issue = client.post(
        f"/api/v1/institutions/{institution_id}/email-verification",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"institutional_email": "owner@students.test.edu"},
    )
    assert issue.status_code == status.HTTP_202_ACCEPTED
    verification_token = sender.messages[-1]["token"]

    wrong_owner = client.post(
        "/api/v1/institutions/email-verification/confirm",
        headers={"Authorization": f"Bearer {other_user_token}"},
        json={"token": verification_token},
    )
    assert wrong_owner.status_code == status.HTTP_400_BAD_REQUEST

    with SessionLocal() as db:
        challenge = db.query(EmailVerificationChallenge).one()
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    expired = client.post(
        "/api/v1/institutions/email-verification/confirm",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"token": verification_token},
    )
    assert expired.status_code == status.HTTP_400_BAD_REQUEST


def test_verification_issuance_is_rate_limited(institution_test_context) -> None:
    client, _, sender, institution_id, _ = institution_test_context
    token = register_and_login(client, "rate-limit@example.com")
    payload = {"institutional_email": "rate@students.test.edu"}
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post(f"/api/v1/institutions/{institution_id}/email-verification", headers=headers, json=payload)
    second = client.post(f"/api/v1/institutions/{institution_id}/email-verification", headers=headers, json=payload)

    assert first.status_code == status.HTTP_202_ACCEPTED
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert len(sender.messages) == 1


def test_my_affiliations_are_owned_by_authenticated_user(institution_test_context) -> None:
    client, _, sender, institution_id, _ = institution_test_context
    token = register_and_login(client, "affiliation@example.com")
    empty = client.get("/api/v1/institutions/me", headers={"Authorization": f"Bearer {token}"})
    assert empty.status_code == status.HTTP_200_OK
    assert empty.json() == []

    client.post(
        f"/api/v1/institutions/{institution_id}/email-verification",
        headers={"Authorization": f"Bearer {token}"},
        json={"institutional_email": "affiliation@students.test.edu"},
    )
    affiliations = client.get("/api/v1/institutions/me", headers={"Authorization": f"Bearer {token}"})
    assert affiliations.status_code == status.HTTP_200_OK
    assert affiliations.json()[0]["institutional_email"] == "affiliation@students.test.edu"
    assert sender.messages[-1]["token"] not in affiliations.text
