"""Unit tests for the OpenAI platform parameters."""

import os
from unittest.mock import patch

import pytest

from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.utils import SecretString


class TestOpenAIPlatformParameters:
    """Tests for the OpenAI platform parameters."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with an API key."""
        api_key = SecretString("test-api-key")
        params = OpenAIPlatformParameters(openai_api_key=api_key)
        assert params.openai_api_key is not None
        assert params.openai_api_key.get_secret_value() == "test-api-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization without an API key when no env var is set."""
        # Mock environment to ensure OPENAI_API_KEY is not set
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            with pytest.raises(
                ValueError,
                match="OPENAI_API_KEY environment variable is required",
            ):
                OpenAIPlatformParameters()

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        api_key = SecretString("test-api-key")
        params = OpenAIPlatformParameters(openai_api_key=api_key)
        dumped = params.model_dump()
        assert "openai_api_key" in dumped
        assert dumped["openai_api_key"] == "test-api-key"
        assert dumped["kind"] == "openai"

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        api_key = SecretString("test-api-key")
        params = OpenAIPlatformParameters(openai_api_key=api_key)
        dumped = params.model_dump(exclude_none=True)
        assert "openai_api_key" in dumped
        assert dumped["openai_api_key"] == "test-api-key"

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        api_key = SecretString("test-api-key")
        params = OpenAIPlatformParameters(openai_api_key=api_key)

        new_api_key = SecretString("new-api-key")
        updated = params.model_copy(update={"openai_api_key": new_api_key})

        assert updated.openai_api_key is not None
        assert updated.openai_api_key.get_secret_value() == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "openai_api_key": "test-api-key",
        }
        params = OpenAIPlatformParameters.model_validate(data)
        assert params.openai_api_key is not None
        assert params.openai_api_key.get_secret_value() == "test-api-key"

    def test_model_validate_with_string_api_key(self) -> None:
        """Test validation with string API key."""
        # The implementation should convert string to SecretString
        data = {
            "openai_api_key": "test-api-key",
        }
        params = OpenAIPlatformParameters.model_validate(data)
        assert isinstance(params.openai_api_key, SecretString)
        assert params.openai_api_key.get_secret_value() == "test-api-key"
