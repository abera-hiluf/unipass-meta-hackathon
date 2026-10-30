from app.core.config import Settings


def test_meta_settings_use_standard_environment_names() -> None:
    configured = Settings(
        _env_file=None,
        JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
        META_API_KEY="synthetic-test-key",
        META_API_BASE_URL="https://api.meta.ai/v1",
        META_SAM_MODEL="sam-3.1",
        META_VISION_MODEL="muse-spark-1.3",
    )

    assert configured.meta_api_key is not None
    assert configured.meta_api_key.get_secret_value() == "synthetic-test-key"
    assert configured.meta_api_base_url == "https://api.meta.ai/v1"
    assert configured.meta_sam_model == "sam-3.1"
    assert configured.meta_vision_model == "muse-spark-1.3"
