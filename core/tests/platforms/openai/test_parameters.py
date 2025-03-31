"""Unit tests for the OpenAI platform parameters."""

import pytest

from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters


class TestOpenAIPlatformParameters:
    """Tests for the OpenAI platform parameters."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        params = OpenAIPlatformParameters(api_key="")
        assert params.api_key == ""

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        assert params.api_key == "test-api-key"

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        dumped = params.model_dump()
        assert dumped == {
            "api_key": "test-api-key",
        }

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        dumped = params.model_dump(exclude_none=True)
        assert dumped == {
            "api_key": "test-api-key",
        }

    def test_model_dump_exclude_unset(self) -> None:
        """Test serialization excluding unset values."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        dumped = params.model_dump(exclude_unset=True)
        assert dumped == {
            "api_key": "test-api-key",
        }

    def test_model_dump_exclude_defaults(self) -> None:
        """Test serialization excluding default values."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        dumped = params.model_dump(exclude_defaults=True)
        assert dumped == {
            "api_key": "test-api-key",
        }

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        params = OpenAIPlatformParameters(api_key="test-api-key")
        updated = params.model_copy(update={"api_key": "new-api-key"})
        assert updated.api_key == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "api_key": "test-api-key",
        }
        params = OpenAIPlatformParameters.model_validate(data)
        assert params.api_key == "test-api-key"

    def test_model_validate_invalid(self) -> None:
        """Test validation with invalid data."""
        data = {
            "api_key": 123,  # Should be string
        }
        with pytest.raises(
            ValueError,
            match="Field api_key must be of type <class 'str'>, got <class 'int'>",
        ):
            OpenAIPlatformParameters.model_validate(data)
