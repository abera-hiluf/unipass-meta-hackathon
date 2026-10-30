from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    app_name: str = "UniPass AI + AgentX"
    app_version: str = "0.1.0"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql://localhost:5432/unipass"

    # Reserved for the future Meta Model API provider. No calls are made here.
    meta_api_key: SecretStr | None = None
    meta_api_base_url: str = "https://api.meta.ai/v1"
    meta_sam_model: str = "sam-3.1"
    meta_vision_model: str = "muse-spark-1.3"
    meta_api_timeout_seconds: float = 20.0

    # Keyed HMAC secret for document identifier hashing (kept outside database)
    document_hmac_secret: str = "dev-unipass-hmac-secret-change-in-prod"

    # JWT Authentication configuration
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    email_provider: str = "none"
    document_storage_provider: str = "local"
    document_storage_path: str = str(BACKEND_DIR / ".local_storage")
    document_max_upload_bytes: int = 5 * 1024 * 1024
    document_analysis_provider: str = "none"
    selfie_max_upload_bytes: int = 2 * 1024 * 1024
    selfie_retention_days: int = 30
    liveness_max_upload_bytes: int = 10 * 1024 * 1024
    liveness_challenge_ttl_seconds: int = 120
    face_match_threshold: float = 0.8

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
