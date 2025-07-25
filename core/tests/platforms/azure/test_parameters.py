"""Unit tests for the AzureOpenAI platform parameters."""

import os
from unittest.mock import patch

import pytest

from agent_platform.core.platforms.azure.parameters import AzureOpenAIPlatformParameters
from agent_platform.core.utils import SecretString


class TestAzureOpenAIPlatformParameters:
    """Tests for the AzureOpenAI platform parameters."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with an API key."""
        api_key = SecretString("test-api-key")
        params = AzureOpenAIPlatformParameters(azure_api_key=api_key)
        assert params.azure_api_key is not None
        assert params.azure_api_key.get_secret_value() == "test-api-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization without an API key when no env var is set."""
        # Mock environment to ensure OPENAI_API_KEY is not set
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            with pytest.raises(
                ValueError,
                match="azure_api_key environment variable is required",
            ):
                AzureOpenAIPlatformParameters()

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        api_key = SecretString("test-api-key")
        params = AzureOpenAIPlatformParameters(azure_api_key=api_key)
        dumped = params.model_dump()
        assert "azure_api_key" in dumped
        assert dumped["azure_api_key"] == "test-api-key"
        assert dumped["kind"] == "azure"

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        api_key = SecretString("test-api-key")
        params = AzureOpenAIPlatformParameters(azure_api_key=api_key)
        dumped = params.model_dump(exclude_none=True)
        assert "azure_api_key" in dumped
        assert dumped["azure_api_key"] == "test-api-key"

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        api_key = SecretString("test-api-key")
        params = AzureOpenAIPlatformParameters(azure_api_key=api_key)

        new_api_key = SecretString("new-api-key")
        updated = params.model_copy(update={"azure_api_key": new_api_key})

        assert updated.azure_api_key is not None
        assert updated.azure_api_key.get_secret_value() == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "azure_api_key": "test-api-key",
        }
        params = AzureOpenAIPlatformParameters.model_validate(data)
        assert params.azure_api_key is not None
        assert params.azure_api_key.get_secret_value() == "test-api-key"

    def test_model_validate_with_string_api_key(self) -> None:
        """Test validation with string API key."""
        # The implementation should convert string to SecretString
        data = {
            "azure_api_key": "test-api-key",
        }
        params = AzureOpenAIPlatformParameters.model_validate(data)
        assert isinstance(params.azure_api_key, SecretString)
        assert params.azure_api_key.get_secret_value() == "test-api-key"
