import pytest

from agent_platform.server.sql_generation.preinstalled_agent import (
    _SQL_GENERATION_AGENT_NAME,
    SQL_GENERATION_AGENT_ARCHITECTURE,
    SQL_GENERATION_AGENT_DESCRIPTION,
    SQL_GENERATION_AGENT_VERSION,
    ensure_sql_generation_agent,
    get_sql_generation_agent,
)

pytest_plugins = ["server.tests.storage_fixtures"]


@pytest.mark.asyncio
async def test_ensure_sql_generation_agent_uses_system_user(sqlite_storage):
    """SQL generation agent should be created for the system user and be idempotent."""
    system_user_id = await sqlite_storage.get_system_user_id()

    # Call twice to ensure idempotency
    await ensure_sql_generation_agent(storage=sqlite_storage)
    await ensure_sql_generation_agent(storage=sqlite_storage)

    # Get the agent by name
    agent = await get_sql_generation_agent(storage=sqlite_storage)
    assert agent is not None
    assert agent.name == _SQL_GENERATION_AGENT_NAME
    assert agent.description == SQL_GENERATION_AGENT_DESCRIPTION
    assert agent.agent_architecture.name == SQL_GENERATION_AGENT_ARCHITECTURE
    assert agent.agent_architecture.version == "2.0.0"
    assert agent.version == SQL_GENERATION_AGENT_VERSION
    assert agent.platform_configs == []
    assert agent.mode == "conversational"
    assert agent.user_id == system_user_id


@pytest.mark.asyncio
async def test_sql_generation_agent_updates_when_version_is_newer(sqlite_storage):
    """If the stored agent has an older version, ensure() should update it."""
    system_user_id = await sqlite_storage.get_system_user_id()

    await ensure_sql_generation_agent(storage=sqlite_storage)
    preinstalled_agent = await get_sql_generation_agent(storage=sqlite_storage)
    assert preinstalled_agent is not None

    # Downgrade the stored version
    downgraded_agent = preinstalled_agent.copy(version="0.9.0")
    await sqlite_storage.upsert_agent(system_user_id, downgraded_agent)

    # Running ensure again should update the version
    await ensure_sql_generation_agent(storage=sqlite_storage)
    updated_agent = await get_sql_generation_agent(storage=sqlite_storage)
    assert updated_agent is not None

    assert updated_agent.agent_id == preinstalled_agent.agent_id
    assert updated_agent.version == SQL_GENERATION_AGENT_VERSION


@pytest.mark.asyncio
async def test_get_sql_generation_agent_returns_existing_agent(sqlite_storage):
    """get_sql_generation_agent should retrieve the agent by name."""
    await ensure_sql_generation_agent(storage=sqlite_storage)

    agent = await get_sql_generation_agent(storage=sqlite_storage)

    assert agent is not None
    assert agent.name == _SQL_GENERATION_AGENT_NAME
    assert agent.version == SQL_GENERATION_AGENT_VERSION
