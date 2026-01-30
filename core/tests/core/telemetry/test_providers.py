"""Tests for OTEL provider abstraction layer."""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.metrics.export import MetricExportResult

from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
    OtlpBasicAuthObservabilitySettings,
    OtlpCustomHeadersObservabilitySettings,
)
from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator
from agent_platform.core.telemetry.providers.factory import OtelProviderFactory
from agent_platform.core.telemetry.providers.grafana import GrafanaProvider
from agent_platform.core.telemetry.providers.langsmith import LangSmithProvider
from agent_platform.core.telemetry.providers.otlp_basic_auth import OtlpBasicAuthProvider
from agent_platform.core.telemetry.providers.otlp_custom_headers import OtlpCustomHeadersProvider


class TestGrafanaProvider:
    """Test GrafanaProvider implementation."""

    @patch("agent_platform.core.telemetry.providers.grafana.GrafanaProvider._create_trace_exporter")
    def test_shutdown(self, mock_create_exporter):
        """Test shutdown cleans up processor."""
        mock_exporter = MagicMock()
        mock_create_exporter.return_value = mock_exporter

        settings = GrafanaObservabilitySettings(
            url="https://grafana.example.com/v1/traces",
            api_token="test-token",
            grafana_instance_id="12345",
        )
        provider = GrafanaProvider(settings)

        # Initialize by getting handler
        handler = provider.get_trace_processor()
        assert handler is not None

        # Shutdown should work
        provider.shutdown()

    def test_force_flush_not_initialized(self):
        """Test force_flush returns True when not initialized."""
        settings = GrafanaObservabilitySettings(
            url="https://grafana.example.com/v1/traces",
            api_token="test-token",
            grafana_instance_id="12345",
        )
        provider = GrafanaProvider(settings)

        # Not initialized yet
        result = provider.force_flush()
        assert result is True


class TestGrafanaProviderMetrics:
    """Test GrafanaProvider metrics support."""

    @patch("agent_platform.core.telemetry.providers.grafana.GrafanaProvider._create_metric_exporter")
    def test_get_metrics_exporter_returns_exporter(self, mock_create_exporter):
        """Test that get_metrics_exporter returns a MetricExporter."""
        mock_exporter = MagicMock()
        mock_create_exporter.return_value = mock_exporter

        settings = GrafanaObservabilitySettings(
            url="https://grafana.example.com",
            api_token="test-token",
            grafana_instance_id="12345",
        )
        provider = GrafanaProvider(settings)

        handler = provider.get_metrics_exporter()

        assert handler is mock_exporter
        mock_create_exporter.assert_called_once()


class TestLangSmithProvider:
    """Test LangSmithProvider implementation."""

    def test_get_metrics_exporter_returns_none(self):
        """Test that LangSmith does not support metrics."""
        settings = LangSmithObservabilitySettings(
            url="https://api.smith.langchain.com",
            project_name="test",
            api_key="test-key",
        )
        provider = LangSmithProvider(settings)

        assert provider.get_metrics_exporter() is None


class TestOtelProviderFactory:
    """Test OtelProviderFactory."""

    def test_create_grafana_from_settings(self):
        """Test creating Grafana provider from ObservabilitySettings."""
        settings = ObservabilitySettings(
            kind="grafana",
            provider_settings=GrafanaObservabilitySettings(
                url="https://grafana.example.com/v1/traces",
                api_token="test-token",
                grafana_instance_id="12345",
            ),
        )
        provider = OtelProviderFactory.create(settings)
        assert isinstance(provider, GrafanaProvider)
        assert provider.provider_kind == "grafana"

    def test_create_langsmith_from_settings(self):
        """Test creating LangSmith provider from ObservabilitySettings."""
        settings = ObservabilitySettings(
            kind="langsmith",
            provider_settings=LangSmithObservabilitySettings(
                url="https://api.smith.langchain.com",
                project_name="test",
                api_key="test-key",
            ),
        )
        provider = OtelProviderFactory.create(settings)
        assert isinstance(provider, LangSmithProvider)
        assert provider.provider_kind == "langsmith"

    def test_unsupported_kind_raises(self):
        """Test that unsupported provider kind raises ValueError."""
        # Create a mock settings object with an unsupported kind
        settings = ObservabilitySettings(
            kind="grafana",  # Use valid kind first to create wrapper
            provider_settings=GrafanaObservabilitySettings(
                url="https://grafana.example.com/v1/traces",
                api_token="test-token",
                grafana_instance_id="12345",
            ),
        )
        # Manually override kind to test error handling
        object.__setattr__(settings, "kind", "unsupported_backend")

        with pytest.raises(ValueError, match="Unsupported provider kind"):
            OtelProviderFactory.create(settings)

    def test_create_otlp_basic_auth_from_settings(self):
        """Test creating OTLP Basic Auth provider from ObservabilitySettings."""
        settings = ObservabilitySettings(
            kind="otlp_basic_auth",
            provider_settings=OtlpBasicAuthObservabilitySettings(
                url="http://localhost:4318",
                username="alloy",
                password="steel",
            ),
        )
        provider = OtelProviderFactory.create(settings)
        assert isinstance(provider, OtlpBasicAuthProvider)
        assert provider.provider_kind == "otlp_basic_auth"

    def test_create_otlp_custom_headers_from_settings(self):
        """Test creating OTLP Custom Headers provider from ObservabilitySettings."""
        settings = ObservabilitySettings(
            kind="otlp_custom_headers",
            provider_settings=OtlpCustomHeadersObservabilitySettings(
                url="http://localhost:4318",
                headers={"Authorization": "Bearer token123"},
            ),
        )
        provider = OtelProviderFactory.create(settings)
        assert isinstance(provider, OtlpCustomHeadersProvider)
        assert provider.provider_kind == "otlp_custom_headers"


class TestOtlpBasicAuthProvider:
    """Test OtlpBasicAuthProvider implementation."""

    def test_force_flush_not_initialized(self):
        """Test force_flush returns True when not initialized."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:4318",
            username="alloy",
            password="steel",
        )
        provider = OtlpBasicAuthProvider(settings)
        result = provider.force_flush()
        assert result is True


class TestOtlpBasicAuthProviderMetrics:
    """Test OtlpBasicAuthProvider metrics support."""

    @patch("agent_platform.core.telemetry.providers.otlp_basic_auth.OtlpBasicAuthProvider._create_metric_exporter")
    def test_get_metrics_exporter_returns_exporter(self, mock_create_exporter):
        """Test that get_metrics_exporter returns a MetricExporter."""
        mock_exporter = MagicMock()
        mock_create_exporter.return_value = mock_exporter

        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:4318",
            username="alloy",
            password="steel",
        )
        provider = OtlpBasicAuthProvider(settings)

        handler = provider.get_metrics_exporter()

        assert handler is mock_exporter
        mock_create_exporter.assert_called_once()


class TestOtlpCustomHeadersProvider:
    """Test OtlpCustomHeadersProvider implementation."""

    def test_force_flush_not_initialized(self):
        """Test force_flush returns True when not initialized."""
        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:4318",
            headers={"Authorization": "Bearer token123"},
        )
        provider = OtlpCustomHeadersProvider(settings)
        result = provider.force_flush()
        assert result is True


class TestOtlpCustomHeadersProviderMetrics:
    """Test OtlpCustomHeadersProvider metrics support."""

    @patch(
        "agent_platform.core.telemetry.providers.otlp_custom_headers.OtlpCustomHeadersProvider._create_metric_exporter"
    )
    def test_get_metrics_exporter_returns_exporter(self, mock_create_exporter):
        """Test that get_metrics_exporter returns a MetricExporter."""
        mock_exporter = MagicMock()
        mock_create_exporter.return_value = mock_exporter

        settings = OtlpCustomHeadersObservabilitySettings(
            url="http://localhost:4318",
            headers={"Authorization": "Bearer token123"},
        )
        provider = OtlpCustomHeadersProvider(settings)

        handler = provider.get_metrics_exporter()

        assert handler is mock_exporter
        mock_create_exporter.assert_called_once()


class TestOtelOrchestratorMetrics:
    """Test OtelOrchestrator metrics export."""

    @pytest.fixture(autouse=True)
    def reset_orchestrator(self):
        """Reset orchestrator singleton before each test."""
        OtelOrchestrator.reset_instance()
        yield
        OtelOrchestrator.reset_instance()

    def test_export_broadcasts_to_all_exporters(self):
        """Test that export() sends metrics to collector and all provider exporters."""
        orchestrator = OtelOrchestrator.get_instance()

        # Create mock collector exporter
        collector_exporter = MagicMock()
        collector_exporter.export.return_value = MetricExportResult.SUCCESS

        # Create mock provider exporters
        provider_exporter1 = MagicMock()
        provider_exporter1.export.return_value = MetricExportResult.SUCCESS
        provider_exporter2 = MagicMock()
        provider_exporter2.export.return_value = MetricExportResult.SUCCESS

        # Inject mock exporters
        orchestrator._collector_metric_exporter = collector_exporter
        orchestrator._metric_exporters = [provider_exporter1, provider_exporter2]

        # Create mock metrics data
        mock_metrics_data = MagicMock()

        result = orchestrator.export(mock_metrics_data, timeout_millis=5000)

        assert result == MetricExportResult.SUCCESS
        collector_exporter.export.assert_called_once()
        provider_exporter1.export.assert_called_once()
        provider_exporter2.export.assert_called_once()

    def test_export_returns_success_when_no_exporters(self):
        """Test that export() returns SUCCESS when no exporters configured."""
        orchestrator = OtelOrchestrator.get_instance()
        orchestrator._metric_exporters = []
        orchestrator._collector_metric_exporter = None

        mock_metrics_data = MagicMock()

        result = orchestrator.export(mock_metrics_data)

        assert result == MetricExportResult.SUCCESS

    def test_export_partial_failure_returns_failure(self):
        """Test that export() returns FAILURE if any exporter fails."""
        orchestrator = OtelOrchestrator.get_instance()

        # Create exporters - one succeeds, one fails with exception
        exporter1 = MagicMock()
        exporter1.export.return_value = MetricExportResult.SUCCESS
        exporter2 = MagicMock()
        exporter2.export.side_effect = Exception("Network error")

        orchestrator._metric_exporters = [exporter1, exporter2]
        orchestrator._collector_metric_exporter = None

        mock_metrics_data = MagicMock()

        result = orchestrator.export(mock_metrics_data)

        # Should return FAILURE because one exporter failed
        assert result == MetricExportResult.FAILURE
        # Both exporters should have been called (best-effort)
        exporter1.export.assert_called_once()
        exporter2.export.assert_called_once()
