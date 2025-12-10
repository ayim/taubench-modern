import pytest

from agent_platform.server.sql_generation.preinstalled_agent import (
    SQL_GENERATION_AGENT_ARCHITECTURE,
    SQL_GENERATION_AGENT_DESCRIPTION,
    SQL_GENERATION_AGENT_METADATA,
    SQL_GENERATION_AGENT_VERSION,
    ensure_sql_generation_agent,
)

pytest_plugins = ["server.tests.storage_fixtures"]


async def _get_sql_generation_agent(storage, user_id: str):
    """Return the SQL generation subagent for the given user."""
    agents = await storage.list_agents(user_id)
    return next(
        agent
        for agent in agents
        # `.items()` gives a set-like view; `<=` checks the required metadata is a subset.
        if SQL_GENERATION_AGENT_METADATA.items() <= (agent.extra.get("metadata") or {}).items()
    )


@pytest.mark.asyncio
async def test_ensure_sql_generation_agent_uses_system_user(sqlite_storage):
    """SQL generation agent should be created for the system user and be idempotent."""
    # Use whatever the storage considers the system user in this environment
    system_user_id = await sqlite_storage.get_system_user_id()

    # Call twice to ensure idempotency
    await ensure_sql_generation_agent(storage=sqlite_storage)
    await ensure_sql_generation_agent(storage=sqlite_storage)

    agents = await sqlite_storage.list_agents(system_user_id)

    # There should be exactly one agent matching the SQL_GENERATION_AGENT_METADATA
    sql_agents = [
        agent
        for agent in agents
        if SQL_GENERATION_AGENT_METADATA.items() <= (agent.extra.get("metadata") or {}).items()
    ]
    assert len(sql_agents) == 1

    agent = sql_agents[0]
    assert SQL_GENERATION_AGENT_DESCRIPTION == agent.description
    assert agent.agent_architecture.name == SQL_GENERATION_AGENT_ARCHITECTURE
    assert agent.agent_architecture.version == "2.0.0"
    assert agent.version == SQL_GENERATION_AGENT_VERSION
    assert agent.platform_configs == []
    metadata = agent.extra.get("metadata", {})
    assert SQL_GENERATION_AGENT_METADATA.items() <= metadata.items()
    assert agent.mode == "conversational"
    # Name is intentionally obfuscated with a UUID suffix; just ensure it's str
    assert isinstance(agent.name, str)
    assert agent.name != ""


@pytest.mark.asyncio
async def test_sql_generation_agent_updates_when_version_is_newer(sqlite_storage):
    """If the stored SQL subagent has an older version, ensure() should bump it."""
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_sql_generation_agent(storage=sqlite_storage)

    preinstalled_agent = await _get_sql_generation_agent(sqlite_storage, system_user_id)

    # Downgrade the stored version
    downgraded_agent = preinstalled_agent.copy(version="0.9.0")
    await sqlite_storage.upsert_agent(system_user_id, downgraded_agent)

    # Running ensure again should update the version back to SQL_SUBAGENT_VERSION
    await ensure_sql_generation_agent(storage=sqlite_storage)

    updated_agent = await _get_sql_generation_agent(sqlite_storage, system_user_id)

    assert updated_agent.agent_id == preinstalled_agent.agent_id
    assert updated_agent.version == SQL_GENERATION_AGENT_VERSION


@pytest.mark.asyncio
async def test_sql_generation_agent_created_when_name_taken(sqlite_storage):
    """If another agent has a colliding name, SQL subagent should still be created."""
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    system_user_id = await sqlite_storage.get_system_user_id()

    # Create an existing agent whose name might collide with our naming pattern
    existing_agent = Agent(
        name="SQL Generation Agent [existing]",
        description="Existing agent",
        user_id=system_user_id,
        runbook_structured=Runbook(raw_text="", content=[]),
        version="0.1.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.experimental_1",
            version="2.0.0",
        ),
        extra={"metadata": {"project": "user"}},
        mode="conversational",
    )
    await sqlite_storage.upsert_agent(system_user_id, existing_agent)

    # ensure_sql_generation_subagent should still create its own agent
    await ensure_sql_generation_agent(storage=sqlite_storage)

    system_agents = [
        agent
        for agent in await sqlite_storage.list_agents(system_user_id)
        if agent.user_id == system_user_id
    ]

    # One existing + one SQL generation agent
    assert len(system_agents) == 2

    sql_agents = [
        agent
        for agent in system_agents
        if SQL_GENERATION_AGENT_METADATA.items() <= (agent.extra.get("metadata") or {}).items()
    ]
    assert len(sql_agents) == 1
    sql_agent = sql_agents[0]
    assert SQL_GENERATION_AGENT_DESCRIPTION == sql_agent.description
    assert sql_agent.agent_architecture.name == SQL_GENERATION_AGENT_ARCHITECTURE
