from datetime import timedelta
import uuid

from fastapi import status
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db import Base, get_db
from app.main import app
from app.models.user import User


@pytest.fixture
def test_engine():
    """In-memory SQLite engine with StaticPool for multithreaded test clients."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Direct database session for assertions and seeding."""
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def client(test_engine):
    """TestClient with get_db dependency overridden to the test engine."""
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Cryptographic and Token Security Tests
# ==============================================================================

def test_argon2_hashing_and_verification() -> None:
    raw_secret = "UltraSecurePassphrase123!"
    hashed = hash_password(raw_secret)

    # Argon2 hashes must start with the standard identifier
    assert hashed.startswith("$argon2id$")
    assert raw_secret not in hashed

    # Valid password verification
    assert verify_password(raw_secret, hashed) is True

    # Invalid password verification
    assert verify_password("WrongPassword!", hashed) is False

    # Corrupted / invalid hash string handling
    assert verify_password(raw_secret, "not-a-valid-argon2-hash") is False


def test_jwt_access_token_creation_and_expiration() -> None:
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, role="student")

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "student"
    assert "exp" in payload
    assert "iat" in payload

    # Test expired token rejection
    expired_token = create_access_token(
        subject=user_id,
        role="student",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


# ==============================================================================
# 2. Registration API Tests
# ==============================================================================

def test_register_user_success(client: TestClient, db_session: Session) -> None:
    payload = {
        "email": "  Student.Pilot@AnnaUniv.edu  ",
        "password": "PilotPassword2026!",
        "role": "student",
    }
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "student.pilot@annauniv.edu"
    assert data["role"] == "student"
    assert data["is_active"] is True
    assert "id" in data
    # Sensitive fields must NEVER be returned in response body
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify database persistence with Argon2 hash
    user_in_db = db_session.get(User, uuid.UUID(data["id"]))
    assert user_in_db is not None
    assert user_in_db.email == "student.pilot@annauniv.edu"
    assert user_in_db.hashed_password.startswith("$argon2id$")
    assert verify_password("PilotPassword2026!", user_in_db.hashed_password) is True


def test_register_duplicate_email_conflict(client: TestClient) -> None:
    payload = {
        "email": "applicant@university.edu",
        "password": "Password123!",
        "role": "student",
    }
    first_res = client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == status.HTTP_201_CREATED

    # Attempt registration with duplicate email in different casing
    second_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "APPLICANT@UNIVERSITY.EDU",
            "password": "AnotherPassword456!",
            "role": "student",
        },
    )
    assert second_res.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in second_res.json()["detail"]


def test_register_validation_errors(client: TestClient) -> None:
    # Short password (< 8 chars)
    short_pw_res = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@email.edu", "password": "short"},
    )
    assert short_pw_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Invalid email syntax
    bad_email_res = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "validPassword123!"},
    )
    assert bad_email_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Unsupported role
    bad_role_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid2@email.edu",
            "password": "validPassword123!",
            "role": "superadmin",
        },
    )
    assert bad_role_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ==============================================================================
# 3. Login API Tests
# ==============================================================================

def test_login_success_and_token_response(client: TestClient) -> None:
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={"email": "login.test@university.edu", "password": "SecurePassword2026!"},
    )

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN.TEST@UNIVERSITY.EDU", "password": "SecurePassword2026!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    body = login_res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

    # Decode and verify token
    token = body["access_token"]
    payload = decode_access_token(token)
    assert payload["role"] == "student"


def test_login_invalid_credentials_returns_generic_error(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "existing@university.edu", "password": "CorrectPassword123!"},
    )

    # Wrong password for existing user
    wrong_pw_res = client.post(
        "/api/v1/auth/login",
        json={"email": "existing@university.edu", "password": "WrongPassword!"},
    )
    assert wrong_pw_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_pw_res.json()["detail"] == "Invalid email or password"

    # Non-existent user email
    unknown_email_res = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@university.edu", "password": "CorrectPassword123!"},
    )
    assert unknown_email_res.status_code == status.HTTP_401_UNAUTHORIZED
    # Error message must be identical to avoid user enumeration
    assert unknown_email_res.json()["detail"] == "Invalid email or password"


def test_login_inactive_user_rejected(client: TestClient, db_session: Session) -> None:
    user = User(
        email="inactive@university.edu",
        hashed_password=hash_password("Password123!"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@university.edu", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert login_res.json()["detail"] == "Invalid email or password"


# ==============================================================================
# 4. Current User (/me) API Tests
# ==============================================================================

def test_get_current_user_me_endpoint(client: TestClient) -> None:
    # 1. Register & Login
    client.post(
        "/api/v1/auth/register",
        json={"email": "me.test@university.edu", "password": "Password12345!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "me.test@university.edu", "password": "Password12345!"},
    )
    token = login_res.json()["access_token"]

    # 2. Query /me with valid Bearer token
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == status.HTTP_200_OK
    user_data = me_res.json()
    assert user_data["email"] == "me.test@university.edu"
    assert user_data["role"] == "student"
    assert "password" not in user_data
    assert "hashed_password" not in user_data


def test_get_current_user_unauthorized(client: TestClient) -> None:
    # Missing Authorization header
    no_auth_res = client.get("/api/v1/auth/me")
    assert no_auth_res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    # Invalid Bearer token
    invalid_token_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.signature"},
    )
    assert invalid_token_res.status_code == status.HTTP_401_UNAUTHORIZED

    # Expired Bearer token
    expired_token = create_access_token(
        subject=str(uuid.uuid4()),
        role="student",
        expires_delta=timedelta(seconds=-10),
    )
    expired_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired_res.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# 5. Domain & Architectural Isolation Assertions
# ==============================================================================

def test_registration_does_not_grant_verified_identity(client: TestClient, db_session: Session) -> None:
    """Registration creates an authentication account only.

    It must NOT automatically create a verified student profile or grant campus-service rights.
    """
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "unverified.student@annauniv.edu", "password": "SecretPassword123!"},
    )
    assert res.status_code == status.HTTP_201_CREATED
    user_id = uuid.UUID(res.json()["id"])

    user = db_session.get(User, user_id)
    assert user is not None
    # No profile exists yet; identity verification has not occurred
    assert user.profile is None
    assert len(user.verification_attempts) == 0
