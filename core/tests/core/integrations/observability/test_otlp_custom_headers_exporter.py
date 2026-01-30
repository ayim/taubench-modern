"""Tests for OTLP Custom Headers observability settings."""

import pytest

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.integrations.observability.models import (
    OtlpCustomHeadersObservabilitySettings,
)


class TestOtlpCustomHeadersSettings:
    """Test OTLP Custom Headers settings validation (pure DTO)."""

    @pytest.mark.parametrize(
        ("missing_field", "provided_fields"),
        [
            ("url", {"headers": {"X-Custom": "value"}}),
            ("headers", {"url": "http://localhost:14318"}),
        ],
    )
    def test_model_validate_requires_fields(self, missing_field: str, provided_fields: dict):
        """Test that model_validate raises if required fields are missing."""
        with pytest.raises(
            ValueError,
            match=f"OTLP Custom Headers settings require '{missing_field}'",
        ):
            OtlpCustomHeadersObservabilitySettings.model_validate(provided_fields)

    def test_model_validate_requires_headers_dict(self):
        """Test that model_validate raises if headers is not a dict."""
        with pytest.raises(
            ValueError,
            match="OTLP Custom Headers settings 'headers' must be an object",
        ):
            OtlpCustomHeadersObservabilitySettings.model_validate(
                {
                    "url": "http://localhost:14318",
                    "headers": "not a dict",
                }
            )

    @pytest.mark.parametrize(
        "header_name",
        [
            "Content-Type",
            "content-type",
            "CONTENT-TYPE",
            "Content-type",
        ],
    )
    def test_disallowed_content_type_header_rejected(self, header_name: str):
        """Test that Content-Type header is rejected regardless of casing."""
        with pytest.raises(
            PlatformHTTPError,
            match=f"{header_name} may not be specified as an HTTP header",
        ):
            OtlpCustomHeadersObservabilitySettings.model_validate(
                {
                    "url": "http://localhost:14318",
                    "headers": {
                        "X-Custom": "value",
                        header_name: "application/json",
                    },
                }
            )

    @pytest.mark.parametrize(
        "header_name",
        [
            "Host",
            "host",
            "HOST",
        ],
    )
    def test_disallowed_host_header_rejected(self, header_name: str):
        """Test that Host header is rejected regardless of casing."""
        with pytest.raises(
            PlatformHTTPError,
            match=f"{header_name} may not be specified as an HTTP header",
        ):
            OtlpCustomHeadersObservabilitySettings.model_validate(
                {
                    "url": "http://localhost:14318",
                    "headers": {
                        "X-Custom": "value",
                        header_name: "example.com",
                    },
                }
            )

    def test_model_dump_redacts_headers(self):
        """Test that model_dump redacts header values by default."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={
                "Authorization": "Bearer token123",
                "X-Custom": "value",
            },
        )

        # Test with redaction (headers values should be redacted)
        dumped = settings.model_dump()
        assert dumped["headers"]["Authorization"] == "**********"
        assert dumped["headers"]["X-Custom"] == "**********"
        assert dumped["url"] == "http://localhost:14318"

        # Test without redaction
        dumped_plain = settings.model_dump(redact_secret=False)
        assert dumped_plain["headers"]["Authorization"] == "Bearer token123"
        assert dumped_plain["headers"]["X-Custom"] == "value"

    def test_model_validate_from_dict(self):
        """Test that model_validate creates settings from dict."""
        data = {
            "url": "http://localhost:14318",
            "headers": {
                "Authorization": "Bearer token",
                "X-Custom": "value",
            },
        }

        settings = OtlpCustomHeadersObservabilitySettings.model_validate(data)

        assert settings.url == "http://localhost:14318"
        assert settings.headers["Authorization"] == "Bearer token"
        assert settings.headers["X-Custom"] == "value"

    def test_model_validate_rejects_non_dict(self):
        """Test that model_validate rejects non-dict input."""
        with pytest.raises(
            ValueError,
            match="OTLP Custom Headers settings payload must be an object",
        ):
            OtlpCustomHeadersObservabilitySettings.model_validate("not a dict")
