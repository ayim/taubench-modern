"""Tests for Grafana observability provider and settings."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
)
from agent_platform.core.telemetry.providers.grafana import GrafanaProvider


class TestGrafanaSettings:
    """Test Grafana settings validation (pure DTO)."""

    def test_requires_api_token(self):
        """Test that model_validate raises if no api_token provided."""
        with pytest.raises(
            ValueError,
            match="Grafana settings require 'api_token'",
        ):
            GrafanaObservabilitySettings.model_validate(
                {
                    "url": "https://otlp.grafana.net/otlp",
                    "grafana_instance_id": "123456",
                }
            )

    def test_requires_instance_id(self):
        """Test that model_validate raises if no grafana_instance_id provided."""
        with pytest.raises(
            ValueError,
            match="Grafana settings require 'grafana_instance_id'",
        ):
            GrafanaObservabilitySettings.model_validate(
                {
                    "url": "https://otlp.grafana.net/otlp",
                    "api_token": "glc_token123",
                }
            )

    def test_model_validate_rejects_disallowed_headers(self):
        """Test that model_validate raises error for disallowed headers."""
        with pytest.raises(
            PlatformHTTPError,
            match="Authorization may not be specified as an HTTP header",
        ):
            GrafanaObservabilitySettings.model_validate(
                {
                    "url": "https://otlp.grafana.net/otlp",
                    "api_token": "glc_test_token",
                    "grafana_instance_id": "999999",
                    "additional_headers": {
                        "X-Custom-Header": "custom-value",
                        "Authorization": "Bearer bad",
                    },
                }
            )

        with pytest.raises(
            PlatformHTTPError,
            match="Content-Type may not be specified as an HTTP header",
        ):
            GrafanaObservabilitySettings.model_validate(
                {
                    "url": "https://otlp.grafana.net/otlp",
                    "api_token": "glc_test_token",
                    "grafana_instance_id": "999999",
                    "additional_headers": {
                        "Content-Type": "application/json",
                    },
                }
            )

        with pytest.raises(
            PlatformHTTPError,
            match="Host may not be specified as an HTTP header",
        ):
            GrafanaObservabilitySettings.model_validate(
                {
                    "url": "https://otlp.grafana.net/otlp",
                    "api_token": "glc_test_token",
                    "grafana_instance_id": "999999",
                    "additional_headers": {
                        "Host": "example.com",
                    },
                }
            )


class TestGrafanaProvider:
    """Test Grafana provider trace exporter creation."""

    @patch("agent_platform.core.network.utils.build_network_session")
    @patch("agent_platform.core.telemetry.providers.grafana.OTLPSpanExporter")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    def test_creates_trace_handler_with_basic_auth(self, mock_processor_class, mock_exporter_class, mock_build_session):
        """Test get_trace_processor creates exporter with Basic Auth header correctly."""
        mock_session = MagicMock()
        mock_build_session.return_value = mock_session
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_token123",
            grafana_instance_id="123456",
        )

        provider = GrafanaProvider(settings)
        handler = provider.get_trace_processor()

        # Verify exporter was created with correct Basic Auth
        expected_auth = base64.b64encode(b"123456:glc_token123").decode()
        mock_exporter_class.assert_called_once_with(
            endpoint="https://otlp.grafana.net/otlp/v1/traces",
            headers={"Authorization": f"Basic {expected_auth}"},
            session=mock_session,
        )
        assert handler == mock_processor

    @patch("agent_platform.core.network.utils.build_network_session")
    @patch("agent_platform.core.telemetry.providers.grafana.OTLPSpanExporter")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    def test_endpoint_normalization(self, mock_processor_class, mock_exporter_class, mock_build_session):
        """Test that endpoint gets /v1/traces suffix added."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()
        mock_processor_class.return_value = MagicMock()

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp/",  # Note: trailing slash
            api_token="glc_token",
            grafana_instance_id="654321",
        )

        provider = GrafanaProvider(settings)
        provider.get_trace_processor()

        # Verify endpoint was normalized (trailing slash removed, /v1/traces added)
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "https://otlp.grafana.net/otlp/v1/traces"

    @patch("agent_platform.core.network.utils.build_network_session")
    @patch("agent_platform.core.telemetry.providers.grafana.OTLPSpanExporter")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    def test_additional_headers_included(self, mock_processor_class, mock_exporter_class, mock_build_session):
        """Test that additional_headers are included in the request."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()
        mock_processor_class.return_value = MagicMock()

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_test_token",
            grafana_instance_id="999999",
            additional_headers={"X-Custom-Header": "custom-value"},
        )

        provider = GrafanaProvider(settings)
        provider.get_trace_processor()

        # Verify additional headers are included
        call_args = mock_exporter_class.call_args
        headers = call_args[1]["headers"]
        assert "Authorization" in headers  # Basic auth should be present
        assert headers["X-Custom-Header"] == "custom-value"

    @patch("agent_platform.core.network.utils.build_network_session")
    @patch("agent_platform.core.telemetry.providers.grafana.OTLPSpanExporter")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    def test_handler_cached(self, mock_processor_class, mock_exporter_class, mock_build_session):
        """Test that get_trace_processor returns cached handler on subsequent calls."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_token",
            grafana_instance_id="123456",
        )

        provider = GrafanaProvider(settings)

        # First call creates handler
        handler1 = provider.get_trace_processor()
        # Second call returns cached handler
        handler2 = provider.get_trace_processor()

        assert handler1 is handler2
        assert mock_processor_class.call_count == 1  # Only created once
