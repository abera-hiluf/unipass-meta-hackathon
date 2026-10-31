import json

import httpx
import pytest

from app.core.config import Settings
from app.services.analysis import MetaDocumentAnalysisAdapter
from app.services.meta_api import MetaAPIError, MetaModelClient


class FakeRequester:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict) -> httpx.Response:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json=self.payload)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
        META_API_KEY="synthetic-test-key",
        META_API_BASE_URL="https://api.meta.ai/v1",
        META_SAM_MODEL="sam-3.1",
        META_VISION_MODEL="muse-spark-1.3",
    )


def test_meta_client_uses_responses_api_and_validates_structured_output() -> None:
    requester = FakeRequester(
        {
            "output_text": json.dumps(
                {
                    "full_name": "Synthetic Student",
                    "date_of_birth": "2000-01-02",
                    "document_type": "passport",
                    "expiration_date": None,
                    "issuing_country": "IN",
                    "document_number": "SYNTHETIC-123",
                    "confidence": 0.91,
                    "portrait_bounds": None,
                }
            )
        }
    )
    client = MetaModelClient(_settings(), requester=requester)

    fields = client.extract_document_fields(b"\xff\xd8\xffsynthetic", "image/jpeg", "passport")

    assert fields.full_name == "Synthetic Student"
    assert requester.calls[0]["url"] == "https://api.meta.ai/v1/responses"
    assert requester.calls[0]["headers"]["Authorization"] == "Bearer synthetic-test-key"
    assert requester.calls[0]["json"]["model"] == "muse-spark-1.3"
    assert requester.calls[0]["json"]["text"]["format"]["type"] == "json_schema"


def test_meta_client_rejects_invalid_model_output() -> None:
    requester = FakeRequester({"output_text": "not-json"})
    client = MetaModelClient(_settings(), requester=requester)

    with pytest.raises(MetaAPIError, match="invalid structured output"):
        client.extract_document_fields(b"synthetic", "image/jpeg", "passport")


def test_meta_document_adapter_hmacs_document_number_without_storing_raw_value() -> None:
    requester = FakeRequester(
        {
            "output_text": json.dumps(
                {
                    "full_name": "Synthetic Student",
                    "date_of_birth": "2000-01-02",
                    "document_type": "passport",
                    "expiration_date": None,
                    "issuing_country": "IN",
                    "document_number": "SYNTHETIC-123",
                    "confidence": 0.91,
                    "portrait_bounds": None,
                }
            )
        }
    )
    result = MetaDocumentAnalysisAdapter(MetaModelClient(_settings(), requester=requester)).analyze(
        b"\xff\xd8\xffsynthetic", "passport"
    )

    assert result.status == "COMPLETED"
    assert result.extracted_document_type == "passport"
    assert result.document_number_hmac is not None
    assert "SYNTHETIC-123" not in result.document_number_hmac


def test_meta_document_adapter_extracts_expiry_and_private_portrait_crop() -> None:
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (200, 200), "white")
    output = BytesIO()
    image.save(output, format="JPEG")
    requester = FakeRequester(
        {
            "output_text": json.dumps(
                {
                    "full_name": "Synthetic Student",
                    "date_of_birth": "2000-01-02",
                    "document_type": "passport",
                    "expiration_date": "2030-01-02",
                    "issuing_country": "IN",
                    "document_number": "SYNTHETIC-123",
                    "confidence": 0.91,
                    "portrait_bounds": [0.1, 0.1, 0.6, 0.8],
                }
            )
        }
    )
    result = MetaDocumentAnalysisAdapter(MetaModelClient(_settings(), requester=requester)).analyze(
        output.getvalue(), "passport"
    )

    assert result.expiration_date.isoformat() == "2030-01-02"
    assert result.portrait_bytes is not None
    with Image.open(BytesIO(result.portrait_bytes)) as portrait:
        assert portrait.size == (100, 140)
    assert result.portrait_extension == ".jpg"
