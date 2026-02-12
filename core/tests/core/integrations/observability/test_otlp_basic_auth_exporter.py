"""Tests for OTLP Basic Auth observability settings."""

import pytest

from agent_platform.core.integrations.observability.models import OtlpBasicAuthObservabilitySettings
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

    def test_model_validate_with_trace_ui_type(self):
        """Test that model_validate correctly parses trace_ui_type."""
        data = {
            "url": "http://localhost:14318",
            "username": "alloy",
            "password": "steel",
            "trace_ui_type": "grafana",
        }

        settings = OtlpBasicAuthObservabilitySettings.model_validate(data)

        assert settings.trace_ui_type == "grafana"

    def test_model_validate_invalid_trace_ui_type(self):
        """Test that model_validate rejects invalid trace_ui_type."""
        data = {
            "url": "http://localhost:14318",
            "username": "alloy",
            "password": "steel",
            "trace_ui_type": "invalid",
        }

        with pytest.raises(ValueError, match="trace_ui_type must be 'grafana', 'jaeger', or 'unknown'"):
            OtlpBasicAuthObservabilitySettings.model_validate(data)

    def test_model_dump_includes_trace_ui_type_when_set(self):
        """Test that model_dump includes trace_ui_type when set."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
            trace_ui_type="jaeger",
        )

        dumped = settings.model_dump()
        assert dumped["trace_ui_type"] == "jaeger"

    def test_model_dump_defaults_trace_ui_type_to_unknown(self):
        """Test that model_dump includes trace_ui_type as 'unknown' when not explicitly set."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
        )

        dumped = settings.model_dump()
        assert dumped["trace_ui_type"] == "unknown"

    def test_get_trace_url_returns_none_when_unknown(self):
        """Test that get_trace_url returns None when trace_ui_type is 'unknown'."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:16686/v1/traces",
            username="alloy",
            password="steel",
            trace_ui_type="unknown",
        )
        assert settings.get_trace_url("abc123") is None

    def test_get_trace_url_jaeger_format(self):
        """Test that get_trace_url returns correct Jaeger URL format."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:16686/v1/traces",
            username="alloy",
            password="steel",
            trace_ui_type="jaeger",
        )
        result = settings.get_trace_url("abc123def456")
        assert result == "http://localhost:16686/trace/abc123def456"

    def test_get_trace_url_grafana_format(self):
        """Test that get_trace_url returns correct Grafana URL format."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:3000/otlp/v1/traces",
            username="alloy",
            password="steel",
            trace_ui_type="grafana",
        )
        result = settings.get_trace_url("abc123def456")
        assert result is not None
        assert result.startswith("http://localhost:3000/explore?")
        assert "orgId=1" in result
        assert "left=" in result
        assert "abc123def456" in result

    def test_get_trace_url_extracts_base_url_correctly(self):
        """Test that get_trace_url extracts base URL (scheme + host + port) from OTLP endpoint."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="https://example.com:8080/v1/traces",
            username="alloy",
            password="steel",
            trace_ui_type="jaeger",
        )
        result = settings.get_trace_url("trace123")
        assert result == "https://example.com:8080/trace/trace123"
