"""Tests for OtelOrchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.integrations import IntegrationScope
from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
)
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator singleton before each test."""
    OtelOrchestrator.reset_instance()
    yield
    OtelOrchestrator.reset_instance()


def create_mock_agent(agent_id: str) -> MagicMock:
    """Helper to create a mock agent."""
    agent = MagicMock()
    agent.agent_id = agent_id
    return agent


def create_langsmith_integration(
    integration_id: str,
    project_name: str = "test-project",
    api_key: str = "test-key",
) -> ObservabilityIntegration:
    """Helper to create LangSmith integration."""
    observability_settings = ObservabilitySettings(
        kind="langsmith",
        provider_settings=LangSmithObservabilitySettings(
            url="https://api.smith.langchain.com",
            project_name=project_name,
            api_key=api_key,
        ),
        is_enabled=True,
    )
    settings = ObservabilityIntegrationSettings.from_observability_settings(observability_settings)
    return ObservabilityIntegration(
        id=integration_id,
        kind="observability",
        settings=settings,
    )


def create_grafana_integration(
    integration_id: str,
    url: str = "https://grafana.io/traces",
    token: str = "test-token",
) -> ObservabilityIntegration:
    """Helper to create Grafana integration."""
    observability_settings = ObservabilitySettings(
        kind="grafana",
        provider_settings=GrafanaObservabilitySettings(
            url=url,
            api_token=token,
            grafana_instance_id="12345",
        ),
        is_enabled=True,
    )
    settings = ObservabilityIntegrationSettings.from_observability_settings(observability_settings)
    return ObservabilityIntegration(
        id=integration_id,
        kind="observability",
        settings=settings,
    )


class TestSingleton:
    """Test OtelOrchestrator singleton behavior."""

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


class TestDeduplication:
    """Test deduplication during cold start."""

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_duplicate_configs_share_processor(self, mock_create_processor):
        """Three integrations with same config should create only 1 processor."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [
            create_langsmith_integration("id1", "prod", "key1"),
            create_langsmith_integration("id2", "prod", "key1"),  # Duplicate
            create_langsmith_integration("id3", "prod", "key1"),  # Duplicate
        ]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)

        def mock_list_scopes(integration_id):
            return AsyncMock(
                return_value=[
                    IntegrationScope(integration_id=integration_id, agent_id=None, scope="global")
                ]
            )()

        mock_storage.list_integration_scopes = mock_list_scopes

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        assert mock_create_processor.call_count == 1

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_different_configs_create_multiple_processors(self, mock_create_processor):
        """Different configs should create separate processors."""
        mock_processor1 = MagicMock()
        mock_processor2 = MagicMock()
        mock_create_processor.side_effect = [mock_processor1, mock_processor2]

        integrations = [
            create_langsmith_integration("id1", "prod", "key1"),
            create_langsmith_integration("id2", "prod", "key2"),  # Different API key
        ]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)

        def mock_list_scopes(integration_id):
            return AsyncMock(
                return_value=[
                    IntegrationScope(integration_id=integration_id, agent_id=None, scope="global")
                ]
            )()

        mock_storage.list_integration_scopes = mock_list_scopes

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        assert mock_create_processor.call_count == 2


class TestSpanRouting:
    """Test span routing with deduplication."""

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_duplicate_integrations_send_span_once(self, mock_create_processor):
        """Agent with 3 duplicate integrations should send span to processor only once."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [
            create_langsmith_integration("id1", "prod", "key1"),
            create_langsmith_integration("id2", "prod", "key1"),
            create_langsmith_integration("id3", "prod", "key1"),
        ]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)

        def mock_list_scopes(integration_id):
            return AsyncMock(
                return_value=[
                    IntegrationScope(integration_id=integration_id, agent_id=None, scope="global")
                ]
            )()

        mock_storage.list_integration_scopes = mock_list_scopes

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        mock_span = MagicMock()
        mock_span.attributes = {"agent_id": "agent-foo"}

        orchestrator.on_end(mock_span)

        assert mock_processor.on_end.call_count == 1

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_mixed_scopes_with_duplicates(self, mock_create_processor):
        """Global + agent-specific duplicates should still deduplicate."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [
            create_langsmith_integration("id1", "prod", "key1"),  # Global
            create_langsmith_integration("id2", "prod", "key1"),  # Global
            create_langsmith_integration("id3", "prod", "key1"),  # Agent-specific
        ]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)

        def mock_list_scopes(integration_id):
            if integration_id in ["id1", "id2"]:
                return AsyncMock(
                    return_value=[
                        IntegrationScope(
                            integration_id=integration_id, agent_id=None, scope="global"
                        )
                    ]
                )()
            else:
                return AsyncMock(
                    return_value=[
                        IntegrationScope(
                            integration_id=integration_id, agent_id="agent-foo", scope="agent"
                        )
                    ]
                )()

        mock_storage.list_integration_scopes = mock_list_scopes

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        mock_span = MagicMock()
        mock_span.attributes = {"agent_id": "agent-foo"}

        orchestrator.on_end(mock_span)

        assert mock_processor.on_end.call_count == 1


class TestReload:
    """Test reload and cache invalidation behavior."""

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_reload_recreates_and_shuts_down_processors(self, mock_create_processor):
        """Every reload recreates all processors and shuts down old ones."""
        mock_processor1 = MagicMock()
        mock_processor2 = MagicMock()
        mock_processor3 = MagicMock()
        mock_processor4 = MagicMock()
        mock_create_processor.side_effect = [
            mock_processor1,
            mock_processor2,
            mock_processor3,
            mock_processor4,
        ]

        integrations = [
            create_langsmith_integration("id1", "prod", "key1"),
            create_grafana_integration("id2", "https://grafana.io/traces", "t1"),
        ]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)

        def mock_list_scopes(integration_id):
            return AsyncMock(
                return_value=[
                    IntegrationScope(integration_id=integration_id, agent_id=None, scope="global")
                ]
            )()

        mock_storage.list_integration_scopes = mock_list_scopes

        orchestrator = OtelOrchestrator.get_instance()

        await orchestrator.reload_from_storage(mock_storage)
        assert mock_create_processor.call_count == 2
        assert mock_processor1.shutdown.call_count == 0

        await orchestrator.reload_from_storage(mock_storage)
        assert mock_create_processor.call_count == 4
        assert mock_processor1.shutdown.call_count == 1
        assert mock_processor2.shutdown.call_count == 1

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_no_scopes_no_processors(self, mock_create_processor):
        """Integrations without scopes should not create processors."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [create_langsmith_integration("id1", "prod", "key1")]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)
        mock_storage.list_integration_scopes = AsyncMock(return_value=[])

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        assert mock_create_processor.call_count == 0

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_empty_reload_clears_all(self, mock_create_processor):
        """Reload with no integrations shuts down all and clears map."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [create_langsmith_integration("id1", "prod", "key1")]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)
        mock_storage.list_integration_scopes = AsyncMock(
            return_value=[IntegrationScope(integration_id="id1", agent_id=None, scope="global")]
        )

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        all_procs = set()
        for procs in orchestrator._agent_id_to_processors.values():
            all_procs.update(procs)
        assert len(all_procs) == 1

        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=[])
        await orchestrator.reload_from_storage(mock_storage)

        all_procs = set()
        for procs in orchestrator._agent_id_to_processors.values():
            all_procs.update(procs)
        assert len(all_procs) == 0
        assert mock_processor.shutdown.call_count == 1

    @pytest.mark.asyncio
    @patch("agent_platform.core.telemetry.otel_orchestrator.OtelOrchestrator._create_processor")
    async def test_new_agent_added_on_reload(self, mock_create_processor):
        """When a new agent is added, reload should include it in routing map."""
        mock_processor = MagicMock()
        mock_create_processor.return_value = mock_processor

        integrations = [create_langsmith_integration("id1", "prod", "key1")]

        mock_storage = MagicMock()
        mock_storage.list_all_agents = AsyncMock(return_value=[create_mock_agent("agent-foo")])
        mock_storage.list_enabled_observability_integrations = AsyncMock(return_value=integrations)
        mock_storage.list_integration_scopes = AsyncMock(
            return_value=[IntegrationScope(integration_id="id1", agent_id=None, scope="global")]
        )

        orchestrator = OtelOrchestrator.get_instance()
        await orchestrator.reload_from_storage(mock_storage)

        # agent-foo should be in the map
        assert "agent-foo" in orchestrator._agent_id_to_processors
        assert "agent-bar" not in orchestrator._agent_id_to_processors

        # Add new agent
        mock_storage.list_all_agents = AsyncMock(
            return_value=[create_mock_agent("agent-foo"), create_mock_agent("agent-bar")]
        )
        await orchestrator.reload_from_storage(mock_storage)

        # Both agents should be in the map
        assert "agent-foo" in orchestrator._agent_id_to_processors
        assert "agent-bar" in orchestrator._agent_id_to_processors
