"""Tests for OtelOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
from agent_platform.core.integrations.observability.models import (
    LangSmithObservabilitySettings,
    ObservabilitySettings,
)
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.otel_orchestrator import OtelOrchestrator


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator singleton before each test."""
    OtelOrchestrator.reset_instance()
    yield
    OtelOrchestrator.reset_instance()


@pytest.fixture
def langsmith_integration() -> ObservabilityIntegration:
    """Create a test LangSmith integration."""
    # Create ObservabilitySettings with is_enabled=True
    observability_settings = ObservabilitySettings(
        kind="langsmith",
        provider_settings=LangSmithObservabilitySettings(
            url="https://api.smith.langchain.com",
            project_name="test-project",
            api_key="test-key",
        ),
        is_enabled=True,
    )
    settings = ObservabilityIntegrationSettings.from_observability_settings(observability_settings)
    return ObservabilityIntegration(
        id="test-integration-1",
        kind="observability",
        settings=settings,
    )


class TestOtelOrchestrator:
    """Test OtelOrchestrator functionality."""

    def test_singleton_instance(self):
        """Test that OtelOrchestrator is a singleton."""
        orchestrator1 = OtelOrchestrator.get_instance()
        orchestrator2 = OtelOrchestrator.get_instance()
        assert orchestrator1 is orchestrator2

    def test_reset_instance(self):
        """Test that reset_instance creates a new instance."""
        orchestrator1 = OtelOrchestrator.get_instance()
        OtelOrchestrator.reset_instance()
        orchestrator2 = OtelOrchestrator.get_instance()
        assert orchestrator1 is not orchestrator2

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_load_integrations(self, mock_create_processor, langsmith_integration):
        """Test loading integrations on startup."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.load_integrations([langsmith_integration])

        # Verify processor was created
        mock_create_processor.assert_called_once_with(langsmith_integration)

        # Verify integration is in maps
        assert langsmith_integration.id in orchestrator._runtime_map
        assert langsmith_integration.id in orchestrator._meta_map

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_reload_integration_creates_processor(
        self, mock_create_processor, langsmith_integration
    ):
        """Test that reload_integration creates a new processor."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.reload_integration(langsmith_integration)

        # Verify processor was created
        mock_create_processor.assert_called_once_with(langsmith_integration)
        assert langsmith_integration.id in orchestrator._runtime_map

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_reload_integration_disabled(self, mock_create_processor, langsmith_integration):
        """Test that disabled integrations are removed."""
        # First load the integration
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.reload_integration(langsmith_integration)
        assert langsmith_integration.id in orchestrator._runtime_map

        # Now disable it
        disabled_observability_settings = ObservabilitySettings(
            kind="langsmith",
            provider_settings=LangSmithObservabilitySettings(
                url="https://api.smith.langchain.com",
                project_name="test-project",
                api_key="test-key",
            ),
            is_enabled=False,
        )
        disabled_settings = ObservabilityIntegrationSettings.from_observability_settings(
            disabled_observability_settings
        )

        disabled_integration = ObservabilityIntegration(
            id=langsmith_integration.id,
            kind="observability",
            settings=disabled_settings,
        )

        orchestrator.reload_integration(disabled_integration)

        # Verify it was removed
        assert langsmith_integration.id not in orchestrator._runtime_map
        assert langsmith_integration.id not in orchestrator._meta_map

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_remove_integration(self, mock_create_processor, langsmith_integration):
        """Test removing an integration."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.reload_integration(langsmith_integration)

        # Remove it
        orchestrator.remove_integration(langsmith_integration.id)

        # Verify it was removed from both maps
        assert langsmith_integration.id not in orchestrator._runtime_map
        assert langsmith_integration.id not in orchestrator._meta_map

        # Verify shutdown was called
        mock_processor.shutdown.assert_called_once()

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_on_end_routes_to_all_processors(self, mock_create_processor, langsmith_integration):
        """Test that on_end routes spans to all processors."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.load_integrations([langsmith_integration])

        # Create a mock span
        mock_span = MagicMock()

        # Call on_end
        orchestrator.on_end(mock_span)

        # Verify processor on_end was called
        mock_processor.on_end.assert_called_once_with(mock_span)

    @patch("agent_platform.core.otel_orchestrator.OtelOrchestrator._create_processor")
    def test_shutdown_clears_maps(self, mock_create_processor, langsmith_integration):
        """Test that shutdown clears all maps and shuts down processors."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        orchestrator = OtelOrchestrator.get_instance()
        orchestrator.load_integrations([langsmith_integration])

        # Shutdown
        orchestrator.shutdown()

        # Verify maps are cleared
        assert len(orchestrator._runtime_map) == 0
        assert len(orchestrator._meta_map) == 0

        # Verify processor shutdown was called
        mock_processor.shutdown.assert_called_once()
