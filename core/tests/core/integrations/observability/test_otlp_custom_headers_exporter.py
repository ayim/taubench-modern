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

    def test_model_validate_with_trace_ui_type(self):
        """Test that model_validate correctly parses trace_ui_type."""
        data = {
            "url": "http://localhost:14318",
            "headers": {"X-Custom": "value"},
            "trace_ui_type": "grafana",
        }

        settings = OtlpCustomHeadersObservabilitySettings.model_validate(data)

        assert settings.trace_ui_type == "grafana"

    def test_model_validate_invalid_trace_ui_type(self):
        """Test that model_validate rejects invalid trace_ui_type."""
        data = {
            "url": "http://localhost:14318",
            "headers": {"X-Custom": "value"},
            "trace_ui_type": "invalid",
        }

        with pytest.raises(ValueError, match="trace_ui_type must be 'grafana', 'jaeger', or 'unknown'"):
            OtlpCustomHeadersObservabilitySettings.model_validate(data)

    def test_model_dump_includes_trace_ui_type_when_set(self):
        """Test that model_dump includes trace_ui_type when set."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={"X-Custom": "value"},
            trace_ui_type="jaeger",
        )

        dumped = settings.model_dump()
        assert dumped["trace_ui_type"] == "jaeger"

    def test_model_dump_defaults_trace_ui_type_to_unknown(self):
        """Test that model_dump includes trace_ui_type as 'unknown' when not explicitly set."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={"X-Custom": "value"},
        )

        dumped = settings.model_dump()
        assert dumped["trace_ui_type"] == "unknown"

    def test_get_trace_url_returns_none_when_unknown(self):
        """Test that get_trace_url returns None when trace_ui_type is 'unknown'."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={"X-Custom": "value"},
            trace_ui_type="unknown",
        )
        assert settings.get_trace_url("abc123") is None

    def test_get_trace_url_returns_url_when_configured(self):
        """Test that get_trace_url returns a URL when trace_ui_type is configured."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:16686/v1/traces",
            headers={"X-Custom": "value"},
            trace_ui_type="jaeger",
        )
        result = settings.get_trace_url("abc123")
        assert result == "http://localhost:16686/trace/abc123"
