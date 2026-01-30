"""Tests for OTLP Basic Auth observability settings."""

import pytest

from agent_platform.core.integrations.observability.models import (
    OtlpBasicAuthObservabilitySettings,
)
from agent_platform.core.utils import SecretString


class TestOtlpBasicAuthSettings:
    """Test OTLP Basic Auth settings validation (pure DTO)."""

    @pytest.mark.parametrize(
        ("missing_field", "provided_fields"),
        [
            ("url", {"username": "alloy", "password": "steel"}),
            ("username", {"url": "http://localhost:14318", "password": "steel"}),
            ("password", {"url": "http://localhost:14318", "username": "alloy"}),
        ],
    )
    def test_model_validate_requires_fields(self, missing_field: str, provided_fields: dict):
        """Test that model_validate raises if required fields are missing."""
        with pytest.raises(
            ValueError,
            match=f"OTLP Basic Auth settings require '{missing_field}'",
        ):
            OtlpBasicAuthObservabilitySettings.model_validate(provided_fields)

    def test_model_dump_redaction(self):
        """Test that model_dump redacts password by default."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
        )

        # Test default redaction
        dumped = settings.model_dump()
        assert dumped["password"] == "**********"
        assert dumped["username"] == "alloy"
        assert dumped["url"] == "http://localhost:14318"

        # Test without redaction
        dumped_plain = settings.model_dump(redact_secret=False)
        assert dumped_plain["password"] == "steel"
        assert dumped_plain["username"] == "alloy"

    def test_model_dump_redaction_with_secret_string(self):
        """Test that model_dump redacts SecretString password correctly."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password=SecretString("steel"),
        )

        # Test default redaction
        dumped = settings.model_dump()
        assert dumped["password"] == "**********"

        # Test without redaction
        dumped_plain = settings.model_dump(redact_secret=False)
        assert dumped_plain["password"] == "steel"

    def test_model_validate_from_dict(self):
        """Test that model_validate creates settings from dict."""
        data = {
            "url": "http://localhost:14318",
            "username": "alloy",
            "password": "steel",
        }

        settings = OtlpBasicAuthObservabilitySettings.model_validate(data)

        assert settings.url == "http://localhost:14318"
        assert settings.username == "alloy"
        assert settings.password == "steel"

    def test_model_validate_rejects_non_dict(self):
        """Test that model_validate rejects non-dict input."""
        with pytest.raises(
            ValueError,
            match="OTLP Basic Auth settings payload must be an object",
        ):
            OtlpBasicAuthObservabilitySettings.model_validate("not a dict")
