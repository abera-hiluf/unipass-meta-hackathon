from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings, settings


class MetaAPIError(RuntimeError):
    """A safe, non-sensitive Meta API failure."""


class MetaRequester(Protocol):
    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response: ...


class ExtractedDocumentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None)
    date_of_birth: str | None = Field(default=None)
    document_type: str | None = Field(default=None)
    expiration_date: str | None = Field(default=None)
    issuing_country: str | None = Field(default=None)
    document_number: str | None = Field(default=None)
    confidence: float | None = Field(default=None, ge=0, le=1)


@dataclass(frozen=True)
class MetaResponse:
    payload: dict[str, Any]


class MetaModelClient:
    """Small Responses API client; disabled unless explicitly selected by config."""

    def __init__(self, config: Settings = settings, requester: MetaRequester | None = None) -> None:
        if config.meta_api_key is None or not config.meta_api_key.get_secret_value():
            raise MetaAPIError("Meta API is not configured")
        self.base_url = config.meta_api_base_url.rstrip("/")
        self.api_key = config.meta_api_key.get_secret_value()
        self.vision_model = config.meta_vision_model
        self.timeout = config.meta_api_timeout_seconds
        self.requester = requester

    def _post(self, payload: dict[str, Any]) -> MetaResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                if self.requester is not None:
                    response = self.requester.post(f"{self.base_url}/responses", headers=headers, json=payload)
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.post(f"{self.base_url}/responses", headers=headers, json=payload)
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    continue
                if response.status_code >= 400:
                    request = response.request or httpx.Request("POST", f"{self.base_url}/responses")
                    raise httpx.HTTPStatusError(
                        "Meta API returned an error status",
                        request=request,
                        response=response,
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise MetaAPIError("Meta API returned an invalid response")
                return MetaResponse(data)
            except (httpx.HTTPError, ValueError, MetaAPIError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 500, 502, 503, 504}:
                    break
        raise MetaAPIError("Meta API request failed") from last_error

    @staticmethod
    def _image_data_url(content: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def extract_document_fields(self, content: bytes, mime_type: str, document_type: str) -> ExtractedDocumentFields:
        schema = {
            "type": "json_schema",
            "name": "identity_document_fields",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "full_name": {"type": ["string", "null"]},
                    "date_of_birth": {"type": ["string", "null"]},
                    "document_type": {"type": ["string", "null"]},
                    "expiration_date": {"type": ["string", "null"]},
                    "issuing_country": {"type": ["string", "null"]},
                    "document_number": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                },
                "required": [
                    "full_name",
                    "date_of_birth",
                    "document_type",
                    "expiration_date",
                    "issuing_country",
                    "document_number",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }
        response = self._post(
            {
                "model": self.vision_model,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Extract only visible fields from this "
                                    f"{document_type} image. Treat all fields as uncertain evidence. "
                                    "Return null when unreadable. Do not infer or approve identity."
                                ),
                            },
                            {
                                "type": "input_image",
                                "image_url": self._image_data_url(content, mime_type),
                            },
                        ],
                    }
                ],
                "text": {"format": schema},
            }
        )
        raw_text = response.payload.get("output_text")
        if not isinstance(raw_text, str):
            for item in response.payload.get("output", []):
                if not isinstance(item, dict):
                    continue
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        raw_text = part["text"]
                        break
                if isinstance(raw_text, str):
                    break
        if not isinstance(raw_text, str):
            raise MetaAPIError("Meta API response did not contain structured output")
        try:
            parsed = json.loads(raw_text)
            return ExtractedDocumentFields.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise MetaAPIError("Meta API returned invalid structured output") from exc
