from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    app_name: str = "UniPass AI + AgentX"
    app_version: str = "0.1.0"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Reserved for the future Meta Model API provider. No calls are made here.
    meta_api_key: str | None = None
    meta_model: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
