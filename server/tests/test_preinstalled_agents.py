import pytest

from agent_platform.server.api.agent_filters import filter_hidden_agents
from agent_platform.server.preinstalled_agents import (
    PREINSTALLED_AGENT_ARCHITECTURE,
    PREINSTALLED_AGENT_METADATA,
    PREINSTALLED_AGENT_VERSION,
    ensure_preinstalled_agents,
)

pytest_plugins = ["server.tests.storage_fixtures"]


def _make_agent(user_id: str, name: str, metadata: dict[str, str]):
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    return Agent(
        name=name,
        description="",
        user_id=user_id,
        runbook_structured=Runbook(raw_text="", content=[]),
        version=PREINSTALLED_AGENT_VERSION,
        platform_configs=[],
        agent_architecture=AgentArchitecture(name=PREINSTALLED_AGENT_ARCHITECTURE, version="2.0.0"),
        extra={"metadata": metadata},
        mode="conversational",
    )


async def _get_preinstalled_agent(storage, user_id: str):
    agents = await storage.list_agents(user_id)
    return next(
        agent
        for agent in agents
        # `.items()` gives a set-like view; `<=` checks the required metadata is a subset.
        if PREINSTALLED_AGENT_METADATA.items() <= (agent.extra.get("metadata") or {}).items()
    )


@pytest.mark.asyncio
async def test_ensure_preinstalled_agent_uses_system_user(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_preinstalled_agents()
    await ensure_preinstalled_agents()

    agents = await sqlite_storage.list_agents(system_user_id)
    assert len(agents) == 1

    agent = agents[0]
    assert agent.name.startswith("My Associate [")
    assert agent.description == "Internal zero-config agent."
    assert agent.agent_architecture.name == PREINSTALLED_AGENT_ARCHITECTURE
    assert agent.agent_architecture.version == "2.0.0"
    assert agent.platform_configs == []
    metadata = agent.extra.get("metadata", {})
    assert PREINSTALLED_AGENT_METADATA.items() <= metadata.items()
    assert agent.mode == "conversational"


@pytest.mark.asyncio
async def test_preinstalled_agent_avoids_production_architectures(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_preinstalled_agents()

    preinstalled_agent = await _get_preinstalled_agent(sqlite_storage, system_user_id)

    # NOTE: these are what I'd call our "production" architectures as of this moment.
    # You'd find these in Studio as `V2.0` or `V2.1` in the architecture selector.
    production_architectures = {
        "agent_platform.architectures.default",
        "agent_platform.architectures.experimental_1",
    }

    assert PREINSTALLED_AGENT_ARCHITECTURE not in production_architectures
    assert preinstalled_agent.agent_architecture.name not in production_architectures


@pytest.mark.asyncio
async def test_hidden_agents_filtered_from_listings(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    visible_agent = _make_agent(
        system_user_id,
        "Visible Agent",
        metadata={"project": "violet"},
    )
    hidden_agent = _make_agent(
        system_user_id,
        "Hidden Agent",
        metadata=PREINSTALLED_AGENT_METADATA.copy(),
    )

    await sqlite_storage.upsert_agent(system_user_id, visible_agent)
    await sqlite_storage.upsert_agent(system_user_id, hidden_agent)

    filtered_agents = filter_hidden_agents(await sqlite_storage.list_agents(system_user_id))
    filtered_names = [agent.name for agent in filtered_agents]

    assert "Visible Agent" in filtered_names
    assert "Hidden Agent" not in filtered_names


@pytest.mark.asyncio
async def test_preinstalled_agent_created_when_name_taken(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    existing_agent = _make_agent(
        system_user_id,
        "My Associate",
        metadata={"project": "violet"},
    )

    await sqlite_storage.upsert_agent(system_user_id, existing_agent)

    await ensure_preinstalled_agents()

    system_agents = [
        agent for agent in await sqlite_storage.list_agents(system_user_id) if agent.user_id == system_user_id
    ]
    assert len(system_agents) == 2

    preinstalled = [
        agent
        for agent in system_agents
        if PREINSTALLED_AGENT_METADATA.items() <= (agent.extra.get("metadata") or {}).items()
    ]

    assert len(preinstalled) == 1
    assert preinstalled[0].name.startswith("My Associate [")


@pytest.mark.asyncio
async def test_preinstalled_agent_does_not_touch_other_users(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    other_user, _ = await sqlite_storage.get_or_create_user("tenant:testing:other:user")
    other_agent = _make_agent(
        other_user.user_id,
        "My Associate",
        metadata={"project": "user"},
    )

    await sqlite_storage.upsert_agent(other_user.user_id, other_agent)

    await ensure_preinstalled_agents()

    system_agents = [
        agent for agent in await sqlite_storage.list_agents(system_user_id) if agent.user_id == system_user_id
    ]
    assert len(system_agents) == 1
    assert PREINSTALLED_AGENT_METADATA.items() <= (system_agents[0].extra.get("metadata") or {}).items()

    user_agents = [
        agent for agent in await sqlite_storage.list_agents(other_user.user_id) if agent.user_id == other_user.user_id
    ]
    assert len(user_agents) == 1
    assert user_agents[0].agent_id == other_agent.agent_id
    assert user_agents[0].extra.get("metadata") == {"project": "user"}


@pytest.mark.asyncio
async def test_preinstalled_agent_allows_additional_metadata(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_preinstalled_agents()

    preinstalled_agent = await _get_preinstalled_agent(sqlite_storage, system_user_id)

    enriched_metadata = (preinstalled_agent.extra.get("metadata") or {}) | {"extra": "keep"}
    enriched_agent = preinstalled_agent.copy(extra={"metadata": enriched_metadata})
    await sqlite_storage.upsert_agent(system_user_id, enriched_agent)

    await ensure_preinstalled_agents()

    updated_agent = await _get_preinstalled_agent(sqlite_storage, system_user_id)

    assert updated_agent.agent_id == preinstalled_agent.agent_id
    assert PREINSTALLED_AGENT_METADATA.items() <= (updated_agent.extra.get("metadata") or {}).items()
    assert (updated_agent.extra.get("metadata") or {}).get("extra") == "keep"


@pytest.mark.asyncio
async def test_preinstalled_agent_updates_when_version_is_newer(sqlite_storage):
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_preinstalled_agents()

    preinstalled_agent = await _get_preinstalled_agent(sqlite_storage, system_user_id)

    downgraded_agent = preinstalled_agent.copy(version="0.9.0")
    await sqlite_storage.upsert_agent(system_user_id, downgraded_agent)

    await ensure_preinstalled_agents()

    updated_agent = await _get_preinstalled_agent(sqlite_storage, system_user_id)

    assert updated_agent.agent_id == preinstalled_agent.agent_id
    assert updated_agent.version == PREINSTALLED_AGENT_VERSION
