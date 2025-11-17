"""Tests for Grafana observability exporter."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
)


class TestGrafanaExporter:
    """Test Grafana exporter creation."""

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_make_exporter_with_basic_auth(self, mock_exporter_class, mock_build_session):
        """Test make_exporter creates Basic Auth header correctly."""
        mock_session = MagicMock()
        mock_build_session.return_value = mock_session
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_token123",
            grafana_instance_id="123456",
        )

        exporter = settings.make_exporter()

        # Verify exporter was created with correct Basic Auth
        # Format: instance_id:api_token
        expected_auth = base64.b64encode(b"123456:glc_token123").decode()
        mock_exporter_class.assert_called_once_with(
            endpoint="https://otlp.grafana.net/otlp/v1/traces",
            headers={"Authorization": f"Basic {expected_auth}"},
            session=mock_session,
        )
        assert exporter == mock_exporter

    def test_make_exporter_requires_api_token(self):
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

    def test_make_exporter_requires_instance_id(self):
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

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_endpoint_normalization(self, mock_exporter_class, mock_build_session):
        """Test that endpoint gets /v1/traces suffix added."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp/",  # Note: trailing slash
            api_token="glc_token",
            grafana_instance_id="654321",
        )

        settings.make_exporter()

        # Verify endpoint was normalized (trailing slash removed, /v1/traces added)
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "https://otlp.grafana.net/otlp/v1/traces"

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_multiple_exporters_get_separate_sessions(
        self, mock_exporter_class, mock_build_session
    ):
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

        settings1 = GrafanaObservabilitySettings(
            url="https://otlp1.grafana.net/otlp",
            api_token="glc_token1",
            grafana_instance_id="111111",
        )

        settings2 = GrafanaObservabilitySettings(
            url="https://otlp2.grafana.net/otlp",
            api_token="glc_token2",
            grafana_instance_id="222222",
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

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_additional_headers_included(self, mock_exporter_class, mock_build_session):
        """Test that additional_headers are included in the request."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_test_token",
            grafana_instance_id="999999",
            additional_headers={"X-Custom-Header": "custom-value"},
        )

        settings.make_exporter()

        # Verify additional headers are included
        call_args = mock_exporter_class.call_args
        headers = call_args[1]["headers"]
        assert "Authorization" in headers  # Basic auth should be present
        assert headers["X-Custom-Header"] == "custom-value"

    def test_model_dump_filters_disallowed_headers(self):
        """Test that model_dump filters out disallowed headers from additional_headers."""
        settings = GrafanaObservabilitySettings(
            url="https://otlp.grafana.net/otlp",
            api_token="glc_test_token",
            grafana_instance_id="999999",
            additional_headers={
                "X-Custom-Header": "custom-value",
                "X-Another-Header": "another-value",
                "Authorization": "Bearer should-be-filtered",
                "Content-Type": "application/json",
                "Host": "example.com",
            },
        )

        with pytest.raises(
            PlatformHTTPError,
            match="Authorization may not be specified as an HTTP header",
        ):
            settings.model_dump(redact_secret=False)

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
