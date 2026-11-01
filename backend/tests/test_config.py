import pytest

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


def test_identity_demo_mode_is_disabled_by_default() -> None:
    configured = Settings(
        _env_file=None,
        JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
    )

    assert configured.identity_demo_mode is False
    assert configured.identity_demo_account_email == "demo@example.com"


@pytest.mark.parametrize("environment", ["production", "staging", "test"])
def test_identity_demo_mode_rejects_non_development_environments(environment: str) -> None:
    with pytest.raises(ValueError, match="IDENTITY_DEMO_MODE may only be enabled"):
        Settings(
            _env_file=None,
            JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
            environment=environment,
            identity_demo_mode=True,
        )


@pytest.mark.parametrize("environment", ["development", "local"])
def test_identity_demo_mode_is_allowed_only_in_local_development(environment: str) -> None:
    configured = Settings(
        _env_file=None,
        JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
        environment=environment,
        identity_demo_mode=True,
    )

    assert configured.identity_demo_mode is True


def test_identity_demo_account_must_use_reserved_domain() -> None:
    with pytest.raises(ValueError, match="IDENTITY_DEMO_ACCOUNT_EMAIL must use the reserved"):
        Settings(
            _env_file=None,
            JWT_SECRET_KEY="unit-test-only-jwt-secret-with-32-plus-bytes",
            identity_demo_mode=True,
            identity_demo_account_email="demo@gmail.com",
        )
