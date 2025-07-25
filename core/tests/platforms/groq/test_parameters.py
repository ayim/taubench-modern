"""Unit tests for the OpenAI platform parameters."""

import os
from unittest.mock import patch

import pytest

from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.utils import SecretString


class TestGroqPlatformParameters:
    """Tests for the OpenAI platform parameters."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with an API key."""
        api_key = SecretString("test-api-key")
        params = GroqPlatformParameters(groq_api_key=api_key)
        assert params.groq_api_key is not None
        assert params.groq_api_key.get_secret_value() == "test-api-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization without an API key when no env var is set."""
        # Mock environment to ensure GROQ_API_KEY is not set
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=True):
            with pytest.raises(
                ValueError,
                match="GROQ_API_KEY environment variable is required",
            ):
                GroqPlatformParameters()

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        api_key = SecretString("test-api-key")
        params = GroqPlatformParameters(groq_api_key=api_key)
        dumped = params.model_dump()
        assert "groq_api_key" in dumped
        assert dumped["groq_api_key"] == "test-api-key"
        assert dumped["kind"] == "groq"

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        api_key = SecretString("test-api-key")
        params = GroqPlatformParameters(groq_api_key=api_key)
        dumped = params.model_dump(exclude_none=True)
        assert "groq_api_key" in dumped
        assert dumped["groq_api_key"] == "test-api-key"

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        api_key = SecretString("test-api-key")
        params = GroqPlatformParameters(groq_api_key=api_key)

        new_api_key = SecretString("new-api-key")
        updated = params.model_copy(update={"groq_api_key": new_api_key})

        assert updated.groq_api_key is not None
        assert updated.groq_api_key.get_secret_value() == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "groq_api_key": "test-api-key",
        }
        params = GroqPlatformParameters.model_validate(data)
        assert params.groq_api_key is not None
        assert params.groq_api_key.get_secret_value() == "test-api-key"

    def test_model_validate_with_string_api_key(self) -> None:
        """Test validation with string API key."""
        # The implementation should convert string to SecretString
        data = {
            "groq_api_key": "test-api-key",
        }
        params = GroqPlatformParameters.model_validate(data)
        assert isinstance(params.groq_api_key, SecretString)
        assert params.groq_api_key.get_secret_value() == "test-api-key"
