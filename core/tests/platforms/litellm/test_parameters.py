"""Tests for the LiteLLM platform parameters."""

import pytest

from agent_platform.core.platforms.litellm.parameters import LiteLLMPlatformParameters
from agent_platform.core.utils import SecretString


class TestLiteLLMPlatformParameters:
    """Behavioural tests covering LiteLLM parameter validation and helpers."""

    def test_init_defaults_alias(self) -> None:
        """Ensure LiteLLM parameters default the alias for display/UI use."""
        params = LiteLLMPlatformParameters(litellm_api_key=SecretString("secret"))
        assert params.alias == "Sema4.ai"

    def test_init_requires_api_key_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure we fail fast when neither the constructor nor
        the environment provides an API key."""
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_BASE_URL", raising=False)

        with pytest.raises(
            ValueError,
            match="LITELLM_API_KEY environment variable is required",
        ):
            LiteLLMPlatformParameters()

    def test_init_reads_api_key_and_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that env vars populate the secret API key and base URL when omitted."""
        monkeypatch.setenv("LITELLM_API_KEY", "env-key")
        monkeypatch.setenv("LITELLM_BASE_URL", "https://router.example/v1")

        params = LiteLLMPlatformParameters()
        assert isinstance(params.litellm_api_key, SecretString)
        assert params.litellm_api_key.get_secret_value() == "env-key"
        assert params.litellm_base_url == "https://router.example/v1"

    def test_init_uses_default_base_url_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Confirm the default LiteLLM base URL is applied whenever no override is defined."""
        monkeypatch.setenv("LITELLM_API_KEY", "env-key")
        monkeypatch.delenv("LITELLM_BASE_URL", raising=False)

        params = LiteLLMPlatformParameters()
        assert params.litellm_base_url == "https://llm.backend.sema4.ai"

    def test_model_dump_serializes_secret_values(self) -> None:
        """Check that model_dump unwraps the SecretString and preserves the base URL."""
        params = LiteLLMPlatformParameters(
            litellm_api_key=SecretString("secret"),
            litellm_base_url="https://router.internal/v1",
        )

        dumped = params.model_dump()

        assert dumped["kind"] == "litellm"
        assert dumped["litellm_api_key"] == "secret"
        assert dumped["litellm_base_url"] == "https://router.internal/v1"

    def test_model_copy_keeps_existing_secret_and_applies_updates(self) -> None:
        """Ensure model_copy carries over current values while applying explicit overrides."""
        params = LiteLLMPlatformParameters(
            litellm_api_key=SecretString("secret"),
            litellm_base_url="https://router.internal/v1",
        )

        updated = params.model_copy(update={"litellm_base_url": "https://alt.router/v1"})

        assert updated.litellm_api_key is not None
        assert updated.litellm_api_key.get_secret_value() == "secret"
        assert updated.litellm_base_url == "https://alt.router/v1"
        # Original params remain unchanged
        assert params.litellm_base_url == "https://router.internal/v1"

    def test_model_validate_with_dict_api_key(self) -> None:
        """Test validation with dict API key (as received from API JSON deserialization)."""
        data = {
            "litellm_api_key": {"value": "test-api-key"},
            "litellm_base_url": "https://router.internal/v1",
        }
        params = LiteLLMPlatformParameters.model_validate(data)
        assert isinstance(params.litellm_api_key, SecretString)
        assert params.litellm_api_key.get_secret_value() == "test-api-key"
