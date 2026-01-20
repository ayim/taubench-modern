"""Tests for OTLP Custom Headers observability exporter."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.integrations.observability.models import (
    OtlpCustomHeadersObservabilitySettings,
)


class TestOtlpCustomHeadersExporter:
    """Test OTLP Custom Headers exporter creation."""

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_make_exporter_with_custom_headers(self, mock_exporter_class, mock_build_session):
        """Test make_exporter passes custom headers correctly."""
        mock_session = MagicMock()
        mock_build_session.return_value = mock_session
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={
                "Authorization": "Bearer token123",
                "X-Custom-Header": "custom-value",
            },
        )

        exporter = settings.make_exporter()

        # Verify exporter was created with custom headers
        mock_exporter_class.assert_called_once_with(
            endpoint="http://localhost:14318/v1/traces",
            headers={
                "Authorization": "Bearer token123",
                "X-Custom-Header": "custom-value",
            },
            session=mock_session,
        )
        assert exporter == mock_exporter

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

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_endpoint_normalization(self, mock_exporter_class, mock_build_session):
        """Test that endpoint gets /v1/traces suffix added."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318/",  # Note: trailing slash
            headers={"X-Custom": "value"},
        )

        settings.make_exporter()

        # Verify endpoint was normalized (trailing slash removed, /v1/traces added)
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "http://localhost:14318/v1/traces"

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_endpoint_already_has_suffix(self, mock_exporter_class, mock_build_session):
        """Test that endpoint with /v1/traces suffix is not duplicated."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318/v1/traces",
            headers={"X-Custom": "value"},
        )

        settings.make_exporter()

        # Verify endpoint was not duplicated
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "http://localhost:14318/v1/traces"

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_multiple_exporters_get_separate_sessions(self, mock_exporter_class, mock_build_session):
        """Test that each exporter gets its own session (not shared).

        This is critical - if exporters share a session, headers from one will
        overwrite headers from another, causing all exporters to send to the
        same backend.
        """
        # Create two different session mocks
        session1 = MagicMock()
        session2 = MagicMock()
        mock_build_session.side_effect = [session1, session2]
        mock_exporter_class.return_value = MagicMock()

        settings1 = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={"X-Instance": "instance1"},
        )

        settings2 = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:24318",
            headers={"X-Instance": "instance2"},
        )

        # Create two exporters
        settings1.make_exporter()
        settings2.make_exporter()

        # Verify build_network_session was called twice (not shared)
        assert mock_build_session.call_count == 2

        # Verify each exporter got a different session
        calls = mock_exporter_class.call_args_list
        assert calls[0][1]["session"] == session1
        assert calls[1][1]["session"] == session2

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

    def test_model_dump_no_redaction_for_headers(self):
        """Test that model_dump returns headers correctly."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:14318",
            headers={
                "Authorization": "Bearer token123",
                "X-Custom": "value",
            },
        )

        # Test with redaction (headers should still be visible)
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
