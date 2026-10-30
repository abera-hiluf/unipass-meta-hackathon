from io import BytesIO
import uuid

import pytest
from PIL import Image

from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.face_matching import FaceMatchAssessment, MockFaceMatchingAdapter, start_face_matching
from app.services.storage import StorageError


def png() -> bytes:
    image = Image.new("RGB", (120, 120), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class Storage:
    def __init__(self, invalid: bool = False) -> None:
        self.objects = {"documents/portraits/portrait.png": png(), "selfies/selfie.png": png()}
        if invalid:
            self.objects["documents/portraits/portrait.png"] = b"invalid"

    def get_object(self, key: str) -> bytes:
        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def put_object(self, key: str, content: bytes, content_type: str) -> None:
        self.objects[key] = content

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


class DB:
    def __init__(self, verification: IdentityVerification) -> None:
        self.verification = verification

    def get(self, model, identifier):
        return self.verification if identifier == self.verification.id else None

    def commit(self) -> None:
        pass

    def refresh(self, instance) -> None:
        pass

    def rollback(self) -> None:
        pass


def setup() -> tuple[User, IdentityVerification, DB]:
    user = User(id=uuid.uuid4(), email="face-match@example.com", hashed_password="synthetic")
    verification = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        status="PENDING",
        portrait_storage_key="documents/portraits/portrait.png",
        selfie_status="SUBMITTED",
        selfie_storage_key="selfies/selfie.png",
    )
    return user, verification, DB(verification)


def test_matching_success_is_controlled_and_does_not_approve_identity() -> None:
    user, verification, db = setup()
    result = start_face_matching(
        db, user, verification.id, Storage(),
        MockFaceMatchingAdapter(FaceMatchAssessment("MATCH", "above_threshold", "mock", 0.95)),
    )
    assert result["status"] == "MATCH"
    assert verification.status != "APPROVED"
    assert "score" not in result


def test_non_match_and_uncertain_scores_are_preserved() -> None:
    user, verification, db = setup()
    result = start_face_matching(
        db, user, verification.id, Storage(),
        MockFaceMatchingAdapter(FaceMatchAssessment("NO_MATCH", "different_face", "mock", 0.12)),
    )
    assert result["status"] == "NO_MATCH"

    user, verification, db = setup()
    result = start_face_matching(
        db, user, verification.id, Storage(),
        MockFaceMatchingAdapter(FaceMatchAssessment("MATCH", "uncertain", "mock", 0.5)),
    )
    assert result["status"] == "REVIEW_REQUIRED"


def test_missing_images_and_invalid_images_never_match() -> None:
    user, verification, db = setup()
    verification.portrait_storage_key = None
    with pytest.raises(Exception) as missing:
        start_face_matching(db, user, verification.id, Storage(), MockFaceMatchingAdapter())
    assert getattr(missing.value, "status_code", None) == 409

    user, verification, db = setup()
    result = start_face_matching(db, user, verification.id, Storage(invalid=True), MockFaceMatchingAdapter(FaceMatchAssessment("MATCH", "bad", "mock", 0.99)))
    assert result["status"] == "FAILED"


def test_unconfigured_provider_returns_review_required() -> None:
    user, verification, db = setup()
    result = start_face_matching(db, user, verification.id, Storage(), MockFaceMatchingAdapter())
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["reason_code"] == "synthetic_uncertain"
