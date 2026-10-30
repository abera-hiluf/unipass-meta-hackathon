from io import BytesIO
from unittest.mock import patch
import uuid

import pytest
from fastapi import UploadFile, status
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from app.db import Base, get_db
from app.main import app
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.documents import create_identity_verification
from app.services.analysis import DocumentAnalysisResult, MockDocumentAnalysisAdapter, get_document_analysis_adapter
from app.services.storage import StorageError, get_storage
from app.core.config import settings


class InMemoryStorage:
    def __init__(self, fail: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail = fail

    def put_object(self, object_key: str, content: bytes, content_type: str) -> None:
        if self.fail:
            raise StorageError("synthetic storage failure")
        self.objects[object_key] = content

    def get_object(self, object_key: str) -> bytes:
        if object_key not in self.objects:
            raise StorageError("synthetic missing object")
        return self.objects[object_key]

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        self.objects.pop(object_key, None)


@pytest.fixture
def document_context():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    storage = InMemoryStorage()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as client:
        yield client, SessionLocal, storage
    app.dependency_overrides.clear()
    engine.dispose()


def register_and_login(client: TestClient, email: str) -> str:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecureDocumentPassword2026!"},
    )
    assert registered.status_code == status.HTTP_201_CREATED
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureDocumentPassword2026!"},
    )
    assert login.status_code == status.HTTP_200_OK
    return login.json()["access_token"]


def pdf_file(name: str = "passport.pdf", content: bytes = b"%PDF-1.7\n%%EOF") -> tuple:
    return (name, content, "application/pdf")


def test_upload_requires_authentication(document_context) -> None:
    client, _, _ = document_context
    response = client.post(
        "/api/v1/identity/documents",
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_valid_upload_is_private_and_pending(document_context) -> None:
    client, SessionLocal, storage = document_context
    token = register_and_login(client, "document-owner@example.com")
    response = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file("original-passport.pdf")},
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["document_type"] == "passport"
    assert body["status"] == "PENDING"
    assert body["reason_code"] == "uploaded_pending_processing"
    assert "document_storage_key" not in body
    assert len(storage.objects) == 1
    object_key = next(iter(storage.objects))
    assert object_key.startswith("documents/")
    assert "original-passport" not in object_key

    with SessionLocal() as db:
        record = db.get(IdentityVerification, uuid.UUID(body["id"]))
        assert record is not None
        assert record.user_id == db.query(User).filter(User.email == "document-owner@example.com").one().id
        assert record.document_storage_key == object_key


def test_unsupported_type_mime_and_signature_are_rejected(document_context) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "format-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    unsupported_type = client.post(
        "/api/v1/identity/documents",
        headers=headers,
        data={"document_type": "drivers_license"},
        files={"file": pdf_file()},
    )
    assert unsupported_type.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    bad_mime = client.post(
        "/api/v1/identity/documents",
        headers=headers,
        data={"document_type": "passport"},
        files={"file": ("passport.pdf", b"%PDF-1.7 synthetic", "image/png")},
    )
    assert bad_mime.status_code == status.HTTP_400_BAD_REQUEST

    bad_signature = client.post(
        "/api/v1/identity/documents",
        headers=headers,
        data={"document_type": "passport"},
        files={"file": ("passport.pdf", b"not a PDF", "application/pdf")},
    )
    assert bad_signature.status_code == status.HTTP_400_BAD_REQUEST


def test_empty_and_oversized_files_are_rejected(document_context, monkeypatch) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "size-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    empty = client.post(
        "/api/v1/identity/documents",
        headers=headers,
        data={"document_type": "passport"},
        files={"file": pdf_file(content=b"")},
    )
    assert empty.status_code == status.HTTP_400_BAD_REQUEST

    monkeypatch.setattr(settings, "document_max_upload_bytes", 10)
    oversized = client.post(
        "/api/v1/identity/documents",
        headers=headers,
        data={"document_type": "passport"},
        files={"file": pdf_file(content=b"%PDF-1.7 too large")},
    )
    assert oversized.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_document_status_has_ownership_protection(document_context) -> None:
    client, _, _ = document_context
    owner_token = register_and_login(client, "owner-status@example.com")
    other_token = register_and_login(client, "other-status@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {owner_token}"},
        data={"document_type": "national_id"},
        files={"file": pdf_file("id.pdf")},
    )
    verification_id = uploaded.json()["id"]

    forbidden = client.get(
        f"/api/v1/identity/documents/{verification_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == status.HTTP_404_NOT_FOUND


def test_storage_failure_does_not_create_record(document_context) -> None:
    client, SessionLocal, _ = document_context
    failing_storage = InMemoryStorage(fail=True)
    app.dependency_overrides[get_storage] = lambda: failing_storage
    token = register_and_login(client, "storage-failure@example.com")
    response = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    with SessionLocal() as db:
        assert db.query(IdentityVerification).count() == 0


def test_database_failure_cleans_up_private_object() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        storage = InMemoryStorage()
        user = User(id=uuid.uuid4(), email="db-failure@example.com", hashed_password="test-hash")
        upload = UploadFile(
            file=BytesIO(b"%PDF-1.7\n%%EOF"),
            filename="passport.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("synthetic database failure")):
            with pytest.raises(Exception) as raised:
                import asyncio

                asyncio.run(create_identity_verification(db, user, upload, "passport", storage))
        assert raised.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert len(storage.deleted) == 1
        assert storage.objects == {}
    engine.dispose()


def png_bytes(size: tuple[int, int] = (120, 120)) -> bytes:
    image = Image.new("RGB", size, color=(120, 160, 200))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_default_analysis_is_explicitly_pending_without_an_ocr_provider(document_context) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "analysis-pending@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "RETRY_REQUIRED"
    assert response.json()["reason_code"] == "analysis_provider_not_configured"
    assert response.json()["extracted_full_name"] is None


def test_mock_analysis_extracts_safe_fields_and_private_portrait(document_context) -> None:
    client, SessionLocal, storage = document_context
    token = register_and_login(client, "analysis-owner@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    result = DocumentAnalysisResult(
        status="COMPLETED",
        reason_code="synthetic_fields_extracted",
        source="mock",
        confidence=0.91,
        full_name="  Synthetic Student  ",
        date_of_birth=__import__("datetime").datetime(2000, 1, 2),
        document_number_hmac="a" * 64,
        portrait_bytes=png_bytes(),
        portrait_extension=".png",
        portrait_content_type="image/png",
    )
    app.dependency_overrides[get_document_analysis_adapter] = lambda: MockDocumentAnalysisAdapter(result=result)
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["extracted_full_name"] == "Synthetic Student"
    assert body["extracted_date_of_birth"] == "2000-01-02"
    assert body["portrait_available"] is True
    assert "document_number_hmac" not in body
    assert any(key.startswith("documents/portraits/") for key in storage.objects)

    with SessionLocal() as db:
        record = db.get(IdentityVerification, uuid.UUID(uploaded.json()["id"]))
        assert record.document_number_hmac == "a" * 64


def test_portrait_not_found_is_explicitly_retryable(document_context) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "portrait-missing@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    result = DocumentAnalysisResult(
        status="RETRY_REQUIRED", reason_code="portrait_not_found", source="mock", confidence=0.4
    )
    app.dependency_overrides[get_document_analysis_adapter] = lambda: MockDocumentAnalysisAdapter(result=result)
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "RETRY_REQUIRED"
    assert response.json()["reason_code"] == "portrait_not_found"
    assert response.json()["portrait_available"] is False


def test_invalid_image_and_storage_retrieval_failures_are_safe(document_context) -> None:
    client, _, storage = document_context
    token = register_and_login(client, "analysis-failure@example.com")
    invalid_image = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "national_id"},
        files={"file": ("id.png", png_bytes((20, 20)), "image/png")},
    )
    assert invalid_image.status_code == status.HTTP_400_BAD_REQUEST

    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "national_id"},
        files={"file": pdf_file("id.pdf")},
    )
    storage.objects.clear()
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_analysis_adapter_failure_marks_request_failed(document_context) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "analysis-adapter-failure@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    app.dependency_overrides[get_document_analysis_adapter] = lambda: MockDocumentAnalysisAdapter(error=True)
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_analysis_ownership_is_enforced(document_context) -> None:
    client, _, _ = document_context
    owner = register_and_login(client, "analysis-owner-access@example.com")
    other = register_and_login(client, "analysis-other-access@example.com")
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {owner}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    response = client.post(
        f"/api/v1/identity/documents/{uploaded.json()['id']}/analyze",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def upload_document_for_selfie(client: TestClient, token: str) -> str:
    uploaded = client.post(
        "/api/v1/identity/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"document_type": "passport"},
        files={"file": pdf_file()},
    )
    assert uploaded.status_code == status.HTTP_201_CREATED
    return uploaded.json()["id"]


def test_selfie_submission_requires_authentication(document_context) -> None:
    client, _, _ = document_context
    response = client.post(
        f"/api/v1/identity/verifications/{uuid.uuid4()}/selfie",
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_valid_selfie_submission_is_private_and_separate_from_liveness(document_context) -> None:
    client, SessionLocal, storage = document_context
    token = register_and_login(client, "selfie-owner@example.com")
    verification_id = upload_document_for_selfie(client, token)
    response = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers={"Authorization": f"Bearer {token}"},
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["selfie_status"] == "SUBMITTED"
    assert body["selfie_reason_code"] == "submitted_for_future_liveness_review"
    assert "selfie_storage_key" not in body
    assert len(storage.objects) == 2  # original document and private selfie
    assert any(key.startswith("selfies/") for key in storage.objects)

    with SessionLocal() as db:
        record = db.get(IdentityVerification, uuid.UUID(verification_id))
        assert record.selfie_storage_key is not None
        assert record.selfie_consent_at is not None
        assert record.status == "PENDING"


def test_selfie_requires_consent_and_completed_capture(document_context) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "selfie-consent@example.com")
    verification_id = upload_document_for_selfie(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    no_consent = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers=headers,
        data={"consent": "false", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert no_consent.status_code == status.HTTP_400_BAD_REQUEST

    incomplete = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers=headers,
        data={"consent": "true", "capture_state": "camera_preview"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert incomplete.status_code == status.HTTP_400_BAD_REQUEST


def test_selfie_invalid_and_oversized_images_are_rejected(document_context, monkeypatch) -> None:
    client, _, _ = document_context
    token = register_and_login(client, "selfie-format@example.com")
    verification_id = upload_document_for_selfie(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    invalid = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers=headers,
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", b"not-an-image", "image/png")},
    )
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST

    monkeypatch.setattr(settings, "selfie_max_upload_bytes", 10)
    oversized = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers=headers,
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert oversized.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_selfie_ownership_and_verification_state_are_enforced(document_context) -> None:
    client, SessionLocal, _ = document_context
    owner = register_and_login(client, "selfie-owner-access@example.com")
    other = register_and_login(client, "selfie-other-access@example.com")
    verification_id = upload_document_for_selfie(client, owner)
    wrong_owner = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers={"Authorization": f"Bearer {other}"},
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert wrong_owner.status_code == status.HTTP_404_NOT_FOUND

    with SessionLocal() as db:
        record = db.get(IdentityVerification, uuid.UUID(verification_id))
        record.status = "APPROVED"
        db.commit()
    invalid_state = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers={"Authorization": f"Bearer {owner}"},
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert invalid_state.status_code == status.HTTP_409_CONFLICT


def test_selfie_storage_failure_is_safe(document_context) -> None:
    client, SessionLocal, _ = document_context
    token = register_and_login(client, "selfie-storage-failure@example.com")
    verification_id = upload_document_for_selfie(client, token)
    failing_storage = InMemoryStorage(fail=True)
    app.dependency_overrides[get_storage] = lambda: failing_storage
    response = client.post(
        f"/api/v1/identity/verifications/{verification_id}/selfie",
        headers={"Authorization": f"Bearer {token}"},
        data={"consent": "true", "capture_state": "captured"},
        files={"file": ("selfie.png", png_bytes(), "image/png")},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    with SessionLocal() as db:
        assert db.get(IdentityVerification, uuid.UUID(verification_id)).selfie_status == "NOT_SUBMITTED"
