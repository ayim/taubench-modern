"""Unit tests for the Google platform parameters."""

import os
from unittest.mock import patch

import pytest

from agent_platform.core.platforms.google.parameters import GooglePlatformParameters
from agent_platform.core.utils import SecretString


class TestGooglePlatformParameters:
    """Tests for the Google platform parameters."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with an API key."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        assert params.google_api_key is not None
        assert params.google_api_key.get_secret_value() == "test-api-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization without an API key when no env var is set."""
        # Mock environment to ensure GOOGLE_API_KEY is not set
        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}, clear=True):
            with pytest.raises(
                ValueError,
                match="GOOGLE_API_KEY environment variable is required",
            ):
                GooglePlatformParameters()

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump()
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"
        assert dumped["kind"] == "google"

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump(exclude_none=True)
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"

    def test_model_dump_exclude_unset(self) -> None:
        """Test serialization excluding unset values."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump(exclude_unset=True)
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"

    def test_model_dump_exclude_defaults(self) -> None:
        """Test serialization excluding default values."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump(exclude_defaults=True)
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)

        new_api_key = SecretString("new-api-key")
        updated = params.model_copy(update={"google_api_key": new_api_key})

        assert updated.google_api_key is not None
        assert updated.google_api_key.get_secret_value() == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "google_api_key": "test-api-key",
        }
        params = GooglePlatformParameters.model_validate(data)
        assert params.google_api_key is not None
        assert params.google_api_key.get_secret_value() == "test-api-key"

    def test_model_validate_with_string_api_key(self) -> None:
        """Test validation with string API key."""
        # The implementation should convert string to SecretString
        data = {
            "google_api_key": "test-api-key",
        }
        params = GooglePlatformParameters.model_validate(data)
        assert isinstance(params.google_api_key, SecretString)
        assert params.google_api_key.get_secret_value() == "test-api-key"
