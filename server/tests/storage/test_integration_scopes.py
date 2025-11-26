"""Tests for integration scope storage methods with additive model."""

from pathlib import Path
from uuid import uuid4

import pytest

from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
)
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.storage.errors import (
    IntegrationScopeNotFoundError,
    InvalidScopeError,
)


def _create_grafana_integration(
    url: str = "https://grafana.example.com/otlp/v1/traces",
    api_token: str = "test-token",
    grafana_instance_id: str = "12345",
    description: str = "Test Grafana integration",
) -> Integration:
    """Helper to create a Grafana integration."""
    settings = ObservabilityIntegrationSettings.from_observability_settings(
        ObservabilitySettings(
            kind="grafana",
            provider_settings=GrafanaObservabilitySettings(
                url=url,
                api_token=SecretString(api_token),
                grafana_instance_id=grafana_instance_id,
            ),
        )
    )
    return Integration(
        id=str(uuid4()),
        kind="observability",
        settings=settings,
        description=description,
        version="1.0",
    )


def _create_langsmith_integration(
    url: str = "https://api.smith.langchain.com",
    project_name: str = "test-project",
    api_key: str = "test-api-key",
    description: str = "Test LangSmith integration",
) -> Integration:
    """Helper to create a LangSmith integration."""
    settings = ObservabilityIntegrationSettings.from_observability_settings(
        ObservabilitySettings(
            kind="langsmith",
            provider_settings=LangSmithObservabilitySettings(
                url=url,
                project_name=project_name,
                api_key=SecretString(api_key),
            ),
        )
    )
    return Integration(
        id=str(uuid4()),
        kind="observability",
        settings=settings,
        description=description,
        version="1.0",
    )


@pytest.fixture
async def sample_integration(storage):
    """Create a sample Grafana integration for testing."""
    integration = _create_grafana_integration()
    await storage.upsert_integration(integration)
    return integration


@pytest.fixture
async def sample_langsmith_integration(storage):
    """Create a sample LangSmith integration for testing."""
    integration = _create_langsmith_integration()
    await storage.upsert_integration(integration)
    return integration


@pytest.fixture
async def sample_agent(storage, tmp_path: Path):
    """Create a sample agent for testing."""
    from server.tests.storage.sample_model_creator import SampleModelCreator

    creator = SampleModelCreator(storage, tmp_path)
    await creator.setup()
    return await creator.obtain_sample_agent("Test Agent")


# ============================================================================
# CRUD Tests
# ============================================================================


@pytest.mark.asyncio
async def test_set_global_scope(storage, sample_integration):
    """Test setting an integration to global scope."""
    scope = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )

    assert scope.integration_id == sample_integration.id
    assert scope.scope == "global"
    assert scope.agent_id is None


@pytest.mark.asyncio
async def test_set_agent_scope(storage, sample_integration, sample_agent):
    """Test setting an integration to agent-specific scope."""
    scope = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )

    assert scope.integration_id == sample_integration.id
    assert scope.scope == "agent"
    assert scope.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_assign_global_scope_with_agent_id_fails(storage, sample_integration, sample_agent):
    """Test that global scope with agent_id fails validation."""
    with pytest.raises(InvalidScopeError, match="global scope must have agent_id=None"):
        await storage.set_integration_scope(
            integration_id=sample_integration.id,
            scope="global",
            agent_id=sample_agent.agent_id,
        )


@pytest.mark.asyncio
async def test_assign_agent_scope_without_agent_id_fails(storage, sample_integration):
    """Test that agent scope without agent_id fails validation."""
    with pytest.raises(InvalidScopeError, match="agent scope must have agent_id set"):
        await storage.set_integration_scope(
            integration_id=sample_integration.id,
            scope="agent",
            agent_id=None,
        )


@pytest.mark.asyncio
async def test_assign_invalid_scope_fails(storage, sample_integration):
    """Test that invalid scope value fails validation."""
    with pytest.raises(InvalidScopeError, match="Invalid scope"):
        await storage.set_integration_scope(
            integration_id=sample_integration.id,
            scope="invalid",
            agent_id=None,
        )


@pytest.mark.asyncio
async def test_set_duplicate_global_scope_idempotent(storage, sample_integration):
    """Test that setting the same integration as global twice is idempotent."""
    # First assignment
    scope1 = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )

    # Second assignment should do nothing (idempotent)
    scope2 = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )

    # Should return the same scope
    assert scope1.integration_id == scope2.integration_id
    assert scope1.agent_id == scope2.agent_id
    assert scope1.scope == scope2.scope


@pytest.mark.asyncio
async def test_set_duplicate_agent_scope_idempotent(storage, sample_integration, sample_agent):
    """Test that setting the same integration to same agent twice is idempotent."""
    # First assignment
    scope1 = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )

    # Second assignment should succeed (idempotent)
    scope2 = await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )

    # Should return the same scope
    assert scope1.integration_id == scope2.integration_id
    assert scope1.agent_id == scope2.agent_id
    assert scope1.scope == scope2.scope


@pytest.mark.asyncio
async def test_list_integration_scopes(storage, sample_integration, sample_agent):
    """Test listing all scope assignments for an integration."""
    # Assign multiple scopes
    await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )
    await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )

    # List scopes
    scopes = await storage.list_integration_scopes(sample_integration.id)

    assert len(scopes) == 2
    scope_types = {scope.scope for scope in scopes}
    assert scope_types == {"global", "agent"}

    # Verify agent_id is set correctly for each scope
    global_scope = next(s for s in scopes if s.scope == "global")
    agent_scope = next(s for s in scopes if s.scope == "agent")
    assert global_scope.agent_id is None
    assert agent_scope.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_delete_integration_scope(storage, sample_integration):
    """Test deleting a scope assignment."""
    # Set scope
    await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )

    # Verify it exists
    scopes = await storage.list_integration_scopes(sample_integration.id)
    assert len(scopes) == 1

    # Delete
    await storage.delete_integration_scope(sample_integration.id, scope="global", agent_id=None)

    # Verify it's gone
    scopes = await storage.list_integration_scopes(sample_integration.id)
    assert len(scopes) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_scope_fails(storage):
    """Test that deleting a nonexistent scope fails."""
    nonexistent_integration_id = str(uuid4())
    with pytest.raises(IntegrationScopeNotFoundError):
        await storage.delete_integration_scope(
            nonexistent_integration_id, scope="global", agent_id=None
        )


@pytest.mark.asyncio
async def test_cascade_delete_integration_removes_scopes(storage, sample_integration):
    """Test that deleting an integration cascades to delete its scopes."""
    # Assign scope
    await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )

    # Verify scope exists
    scopes_before = await storage.list_integration_scopes(sample_integration.id)
    assert len(scopes_before) == 1

    # Delete integration (should cascade to delete scope due to ON DELETE CASCADE)
    await storage.delete_integration_by_id(sample_integration.id)

    # Verify scope is deleted
    scopes_after = await storage.list_integration_scopes(sample_integration.id)
    assert len(scopes_after) == 0


# ============================================================================
# Additive Query Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_observability_integrations_for_agent_basic_scopes(
    storage, sample_integration, sample_langsmith_integration, sample_agent
):
    """Test getting integrations with various basic scope configurations."""
    # Case 1: No scopes - empty list
    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    assert len(integrations) == 0

    # Case 2: Single global scope
    await storage.set_integration_scope(
        integration_id=sample_integration.id,
        scope="global",
        agent_id=None,
    )
    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    assert len(integrations) == 1
    assert integrations[0].id == sample_integration.id

    # Case 3: Multiple global scopes (different providers)
    await storage.set_integration_scope(
        integration_id=sample_langsmith_integration.id,
        scope="global",
        agent_id=None,
    )
    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    assert len(integrations) == 2
    integration_ids = {i.id for i in integrations}
    assert sample_integration.id in integration_ids
    assert sample_langsmith_integration.id in integration_ids

    # Case 4: Global + agent-specific (additive across levels)
    grafana_third = _create_grafana_integration(
        url="https://agent.example.com/otlp/v1/traces",
        api_token="agent-token",
        grafana_instance_id="agent",
        description="Agent-specific Grafana",
    )
    await storage.upsert_integration(grafana_third)
    await storage.set_integration_scope(
        integration_id=grafana_third.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )
    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    # Should get all 3 (2 global + 1 agent)
    assert len(integrations) == 3
    integration_ids = {i.id for i in integrations}
    assert sample_integration.id in integration_ids
    assert sample_langsmith_integration.id in integration_ids
    assert grafana_third.id in integration_ids


@pytest.mark.asyncio
async def test_get_observability_integrations_additive_no_deduplication_by_provider(
    storage, sample_agent
):
    """Test additive model with no de-duplication: same provider at multiple levels/scopes."""
    # Create three Grafana integrations (same provider, different instances)
    grafana_global = _create_grafana_integration(
        url="https://global.example.com/otlp/v1/traces",
        api_token="global-token",
        grafana_instance_id="global",
        description="Grafana Global",
    )

    grafana_global_2 = _create_grafana_integration(
        url="https://global2.example.com/otlp/v1/traces",
        api_token="global-token-2",
        grafana_instance_id="global2",
        description="Grafana Global 2",
    )

    grafana_agent = _create_grafana_integration(
        url="https://agent.example.com/otlp/v1/traces",
        api_token="agent-token",
        grafana_instance_id="agent",
        description="Grafana Agent",
    )

    await storage.upsert_integration(grafana_global)
    await storage.upsert_integration(grafana_global_2)
    await storage.upsert_integration(grafana_agent)

    # Test 1: Two global Grafanas (same provider, both global - NO de-duplication)
    await storage.set_integration_scope(
        integration_id=grafana_global.id,
        scope="global",
        agent_id=None,
    )
    await storage.set_integration_scope(
        integration_id=grafana_global_2.id,
        scope="global",
        agent_id=None,
    )

    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    assert len(integrations) == 2  # Both Grafanas returned
    integration_ids = {i.id for i in integrations}
    assert grafana_global.id in integration_ids
    assert grafana_global_2.id in integration_ids

    # Test 2: Global + agent-specific Grafana (same provider, different levels - NO override!)
    await storage.set_integration_scope(
        integration_id=grafana_agent.id,
        scope="agent",
        agent_id=sample_agent.agent_id,
    )

    integrations = await storage.get_observability_integrations_for_agent(sample_agent.agent_id)
    # Should get ALL 3 Grafanas (additive, agent-specific does NOT override global)
    assert len(integrations) == 3
    integration_ids = {i.id for i in integrations}
    assert grafana_global.id in integration_ids
    assert grafana_global_2.id in integration_ids
    assert grafana_agent.id in integration_ids
