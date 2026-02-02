"""Tests for OTEL provider abstraction layer."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
    OtlpBasicAuthObservabilitySettings,
    OtlpCustomHeadersObservabilitySettings,
)
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
