from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.thread import Thread
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    AgentWithNameAlreadyExistsError,
    ThreadNotFoundError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_agent_by_name(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert the agent and then retrieve by its name.
    await storage.upsert_agent(sample_user_id, sample_agent)
    agent = await storage.get_agent_by_name(sample_user_id, sample_agent.name)
    assert agent is not None
    assert agent.agent_id == sample_agent.agent_id
    assert agent.name == sample_agent.name

    # Look up a non-existent agent should raise an error.
    with pytest.raises(AgentNotFoundError):
        await storage.get_agent_by_name(sample_user_id, "Not Found")


@pytest.mark.asyncio
async def test_agent_crud_operations(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Create (via upsert)
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Read
    retrieved_agent = await storage.get_agent(sample_user_id, sample_agent.agent_id)
    assert retrieved_agent is not None
    assert retrieved_agent.agent_id == sample_agent.agent_id
    assert retrieved_agent.name == sample_agent.name

    # Update the agent name.
    updated_agent = Agent.model_validate(
        sample_agent.model_dump() | {"name": "Updated Agent Name"},
    )
    await storage.upsert_agent(sample_user_id, updated_agent)
    retrieved_updated = await storage.get_agent(
        sample_user_id, sample_agent.agent_id,
    )
    assert retrieved_updated is not None
    assert retrieved_updated.name == "Updated Agent Name"

    # Delete the agent.
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)
    with pytest.raises(AgentNotFoundError):
        await storage.get_agent(sample_user_id, sample_agent.agent_id)


@pytest.mark.asyncio
async def test_agent_list_all(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert an agent for the default user.
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create a second user and an agent for that user.
    other_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:other_user_all_agents",
    )
    other_agent = Agent(
        user_id=other_user.user_id,
        agent_id=str(uuid4()),
        name="Other Agent",
        description="Other Description",
        runbook=sample_agent.runbook,
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=sample_agent.action_packages,
        agent_architecture=sample_agent.agent_architecture,
        question_groups=sample_agent.question_groups,
        observability_configs=sample_agent.observability_configs,
        platform_configs=sample_agent.platform_configs,
        extra=sample_agent.extra,
    )
    await storage.upsert_agent(other_user.user_id, other_agent)

    # List all agents across users.
    all_agents = await storage.list_all_agents()
    agent_ids = {agent.agent_id for agent in all_agents}
    assert sample_agent.agent_id in agent_ids
    assert other_agent.agent_id in agent_ids


@pytest.mark.asyncio
async def test_agent_list(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert an agent and then list agents for that user.
    await storage.upsert_agent(sample_user_id, sample_agent)
    agents = await storage.list_agents(sample_user_id)
    assert len(agents) == 1
    assert agents[0].agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_system_user_access(
    storage: PostgresStorage, sample_agent: Agent,
) -> None:
    # Insert an agent under a regular user.
    regular_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:regular_user",
    )
    await storage.upsert_agent(regular_user.user_id, sample_agent)
    # The system user should be allowed to access this agent.
    system_user_id: str = await storage.get_system_user_id()
    if system_user_id:
        system_accessed_agent = await storage.get_agent(
            system_user_id, sample_agent.agent_id,
        )
        assert system_accessed_agent is not None
        assert system_accessed_agent.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_regular_user_access(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert an agent for the current (regular) user.
    await storage.upsert_agent(sample_user_id, sample_agent)
    regular_accessed_agent = await storage.get_agent(
        sample_user_id, sample_agent.agent_id,
    )
    assert regular_accessed_agent is not None
    assert regular_accessed_agent.agent_id == sample_agent.agent_id

    # A different (non-system) user should not have access to this agent.
    other_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:other_user",
    )
    with pytest.raises(UserAccessDeniedError):
        await storage.get_agent(other_user.user_id, sample_agent.agent_id)


@pytest.mark.asyncio
async def test_agent_delete_cascades_threads(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    # Create an agent and an associated thread.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    # Verify the thread exists.
    existing_thread = await storage.get_thread(
        sample_user_id, sample_thread.thread_id,
    )
    assert existing_thread is not None

    # Delete the agent; threads should be cascaded (removed).
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)
    with pytest.raises(ThreadNotFoundError):
        await storage.get_thread(sample_user_id, sample_thread.thread_id)


@pytest.mark.asyncio
async def test_agent_duplicate_name_constraint(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert the first agent.
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Create a duplicate with the same name (ignoring case).
    duplicate_agent = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "test agent"},
    )
    with pytest.raises(AgentWithNameAlreadyExistsError):
        await storage.upsert_agent(sample_user_id, duplicate_agent)


@pytest.mark.asyncio
async def test_agent_case_insensitive_lookup(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Insert the agent.
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Look up the agent using lower-case and upper-case variations.
    agent_lower = await storage.get_agent_by_name(
        sample_user_id, sample_agent.name.lower(),
    )
    agent_upper = await storage.get_agent_by_name(
        sample_user_id, sample_agent.name.upper(),
    )
    assert agent_lower is not None
    assert agent_upper is not None
    assert agent_lower.agent_id == sample_agent.agent_id
    assert agent_upper.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_invalid_json_metadata(
    storage: PostgresStorage, sample_user_id: str, sample_agent: Agent,
) -> None:
    # Attempt to insert an agent with invalid (unserializable) JSON metadata.
    invalid_agent = Agent.model_validate(
        sample_agent.model_dump() | {"extra": {"invalid": set([1, 2, 3])}},
    )
    with pytest.raises((TypeError, ValueError)):
        await storage.upsert_agent(sample_user_id, invalid_agent)


@pytest.mark.asyncio
async def test_agent_filter_by_user(
    storage: PostgresStorage, sample_agent: Agent,
) -> None:
    # Create an agent for user A.
    user_a, _ = await storage.get_or_create_user(sub="tenant:testing:user:user_a")
    agent_a = Agent.model_validate(
        sample_agent.model_dump()
        | {"agent_id": str(uuid4()), "name": "User A Agent", "user_id": user_a.user_id},
    )
    await storage.upsert_agent(user_a.user_id, agent_a)

    # Create an agent for user B.
    user_b, _ = await storage.get_or_create_user(sub="tenant:testing:user:user_b")
    agent_b = Agent.model_validate(
        sample_agent.model_dump()
        | {"agent_id": str(uuid4()), "name": "User B Agent", "user_id": user_b.user_id},
    )
    await storage.upsert_agent(user_b.user_id, agent_b)

    # List agents for user A only.
    agents_a = await storage.list_agents(user_a.user_id)
    agent_ids_a = {agent.agent_id for agent in agents_a}
    assert agent_a.agent_id in agent_ids_a
    assert agent_b.agent_id not in agent_ids_a
