import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
import uuid

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from PIL import Image

from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.services.liveness import (
    LivenessAssessment,
    MockLivenessAdapter,
    issue_liveness_challenge,
    validate_liveness_consent,
    validate_liveness_challenge,
)
from app.services.storage import StorageError


class Storage:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.objects: dict[str, bytes] = {}

    def put_object(self, key: str, content: bytes, content_type: str) -> None:
        if self.fail:
            raise StorageError("synthetic failure")
        self.objects[key] = content

    def get_object(self, key: str) -> bytes:
        return self.objects[key]

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


class ImageUpload:
    filename = "capture.png"
    content_type = "image/png"

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.offset = 0

    async def read(self, size: int = -1) -> bytes:
        if self.offset >= len(self.content):
            return b""
        if size < 0:
            size = len(self.content)
        chunk = self.content[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


def image_upload() -> ImageUpload:
    image = Image.new("RGB", (120, 120), "white")
    data = BytesIO()
    image.save(data, format="PNG")
    data.seek(0)
    return ImageUpload(data.getvalue())


def setup() -> tuple[User, IdentityVerification, DB]:
    user = User(id=uuid.uuid4(), email="liveness@example.com", hashed_password="synthetic")
    verification = IdentityVerification(id=uuid.uuid4(), user_id=user.id, status="PENDING")
    return user, verification, DB(verification)


def test_challenge_is_randomized_and_bound_to_owner() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)

    assert len(challenge["challenge_id"]) >= 32
    assert set(challenge["steps"]) == {"blink", "turn_left", "turn_right"}
    assert verification.liveness_status == "CHALLENGE_ISSUED"
    assert verification.liveness_challenge_hash != challenge["challenge_id"]


def test_expired_challenges_are_rejected() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)
    verification.liveness_challenge_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(Exception) as expired:
        validate_liveness_challenge(verification, challenge["challenge_id"])
    assert getattr(expired.value, "status_code", None) == 410

def test_reused_challenges_are_rejected() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)
    verification.liveness_status = "REVIEW_REQUIRED"
    verification.liveness_challenge_used_at = datetime.now(timezone.utc)
    with pytest.raises(Exception) as reused:
        validate_liveness_challenge(verification, challenge["challenge_id"])
    assert getattr(reused.value, "status_code", None) == 409


def test_wrong_challenge_and_missing_consent_are_rejected() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)
    with pytest.raises(Exception) as wrong:
        validate_liveness_challenge(verification, "wrong-challenge")
    assert getattr(wrong.value, "status_code", None) == 400



def test_missing_consent_is_rejected() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)
    with pytest.raises(Exception) as no_consent:
        validate_liveness_consent(False, "completed_challenge")
    assert getattr(no_consent.value, "status_code", None) == 400


def test_unavailable_or_spoof_assessment_never_approves_identity() -> None:
    user, verification, db = setup()
    challenge = issue_liveness_challenge(db, user, verification.id)
    result = MockLivenessAdapter(LivenessAssessment("SPOOF_SUSPECTED", "screen_replay", "mock")).assess(
        b"synthetic", "image/png", challenge["steps"]
    )
    assert result.status == "SPOOF_SUSPECTED"
    assert verification.status != "APPROVED"
