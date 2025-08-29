from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
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
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
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
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
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
        sample_user_id,
        sample_agent.agent_id,
    )
    assert retrieved_updated is not None
    assert retrieved_updated.name == "Updated Agent Name"

    # patch
    await storage.patch_agent(
        sample_user_id,
        sample_agent.agent_id,
        "Updated Agent Name (Patch)",
        "Updated Agent Description (Patch)",
    )
    retrieved_updated = await storage.get_agent(
        sample_user_id,
        sample_agent.agent_id,
    )
    assert retrieved_updated.name == "Updated Agent Name (Patch)"
    assert retrieved_updated.description == "Updated Agent Description (Patch)"

    # Delete the agent.
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)
    with pytest.raises(AgentNotFoundError):
        await storage.get_agent(sample_user_id, sample_agent.agent_id)


@pytest.mark.asyncio
async def test_update_agent_prop_not_name(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    # Create an agent
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Update a non-name property
    updated_agent = Agent.model_validate(
        sample_agent.model_dump() | {"description": "Updated Description"},
    )
    await storage.upsert_agent(sample_user_id, updated_agent)

    # Verify the update
    retrieved_updated = await storage.get_agent(
        sample_user_id,
        sample_agent.agent_id,
    )
    assert retrieved_updated is not None
    assert retrieved_updated.description == "Updated Description"


@pytest.mark.asyncio
async def test_agent_list_all(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
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
        runbook_structured=sample_agent.runbook_structured,
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
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    # Insert an agent and then list agents for that user.
    await storage.upsert_agent(sample_user_id, sample_agent)
    agents = await storage.list_agents(sample_user_id)
    assert len(agents) == 1
    assert agents[0].agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_system_user_access(
    storage: PostgresStorage,
    sample_agent: Agent,
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
            system_user_id,
            sample_agent.agent_id,
        )
        assert system_accessed_agent is not None
        assert system_accessed_agent.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_regular_user_access(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    this_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:this_user",
    )
    # Insert an agent for the current (regular) user.
    await storage.upsert_agent(this_user.user_id, sample_agent)
    regular_accessed_agent = await storage.get_agent(
        this_user.user_id,
        sample_agent.agent_id,
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
        sample_user_id,
        sample_thread.thread_id,
    )
    assert existing_thread is not None

    # Delete the agent; threads should be cascaded (removed).
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)
    with pytest.raises(ThreadNotFoundError):
        await storage.get_thread(sample_user_id, sample_thread.thread_id)


@pytest.mark.asyncio
async def test_agent_duplicate_name_constraint(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
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
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    # Insert the agent.
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Look up the agent using lower-case and upper-case variations.
    agent_lower = await storage.get_agent_by_name(
        sample_user_id,
        sample_agent.name.lower(),
    )
    agent_upper = await storage.get_agent_by_name(
        sample_user_id,
        sample_agent.name.upper(),
    )
    assert agent_lower is not None
    assert agent_upper is not None
    assert agent_lower.agent_id == sample_agent.agent_id
    assert agent_upper.agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_invalid_json_metadata(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    # Attempt to insert an agent with invalid (unserializable) JSON metadata.
    invalid_agent = Agent.model_validate(
        sample_agent.model_dump() | {"extra": {"invalid": set([1, 2, 3])}},
    )
    with pytest.raises((TypeError, ValueError)):
        await storage.upsert_agent(sample_user_id, invalid_agent)


@pytest.mark.asyncio
async def test_agent_filter_by_user(
    storage: PostgresStorage,
    sample_agent: Agent,
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


@pytest.mark.asyncio
async def test_agent_mcp_server_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test MCP server operations including association, retrieval, and updates."""
    # Create MCP servers first
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.API)

    # Get the server IDs
    servers_dict = await storage.list_mcp_servers()
    server_ids = list(servers_dict.keys())
    assert len(server_ids) == 2

    # Create agent without MCP server associations
    agent = Agent.model_validate(sample_agent.model_dump() | {"mcp_server_ids": []})
    await storage.upsert_agent(sample_user_id, agent)

    # Initially, agent should have no MCP server associations
    initial_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert initial_ids == []

    # Associate MCP servers with the agent
    await storage.associate_mcp_servers_with_agent(agent.agent_id, server_ids)

    # Verify the associations were created
    associated_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert len(associated_ids) == 2
    assert set(associated_ids) == set(server_ids)

    # Test updating associations (should replace existing ones)
    new_server_ids = [server_ids[0]]  # Only keep the first server
    await storage.associate_mcp_servers_with_agent(agent.agent_id, new_server_ids)

    updated_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert len(updated_ids) == 1
    assert updated_ids == new_server_ids

    # Test with agent that has no MCP servers
    agent_without_mcp = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Test Agent Without MCP",
            "mcp_server_ids": [],
        }
    )
    await storage.upsert_agent(sample_user_id, agent_without_mcp)

    empty_ids = await storage.get_agent_mcp_server_ids(agent_without_mcp.agent_id)
    assert empty_ids == []


@pytest.mark.asyncio
async def test_agent_mcp_server_population(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test populating MCP servers from different sources (join table and JSON)."""
    # Create MCP server for join table association
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    servers_dict = await storage.list_mcp_servers()
    server_id = next(iter(servers_dict.keys()))

    # Test 1: Agent with join table associations only
    agent_join = Agent.model_validate(sample_agent.model_dump() | {"mcp_server_ids": [server_id]})
    await storage.upsert_agent(sample_user_id, agent_join)
    await storage.associate_mcp_servers_with_agent(agent_join.agent_id, [server_id])

    populated_agent_join = await storage._populate_agent_mcp_servers(agent_join)
    assert populated_agent_join.mcp_server_ids == [server_id]
    assert populated_agent_join.mcp_servers == []

    # Test 2: Agent with JSON-based MCP servers only
    agent_json = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "JSON Agent",
            "mcp_server_ids": [],
            "mcp_servers": [sample_mcp_server_stdio.model_dump()],
        }
    )
    await storage.upsert_agent(sample_user_id, agent_json)

    populated_agent_json = await storage._populate_agent_mcp_servers(agent_json)
    assert populated_agent_json.mcp_server_ids == []
    assert len(populated_agent_json.mcp_servers) == 1
    assert populated_agent_json.mcp_servers[0].name == sample_mcp_server_stdio.name

    # Test 3: Agent with both join table and JSON-based servers
    agent_both = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Both Agent",
            "mcp_server_ids": [server_id],
            "mcp_servers": [sample_mcp_server_stdio.model_dump()],
        }
    )
    await storage.upsert_agent(sample_user_id, agent_both)
    await storage.associate_mcp_servers_with_agent(agent_both.agent_id, [server_id])

    populated_agent_both = await storage._populate_agent_mcp_servers(agent_both)
    assert populated_agent_both.mcp_server_ids == [server_id]
    assert len(populated_agent_both.mcp_servers) == 1
    assert populated_agent_both.mcp_servers[0].name == sample_mcp_server_stdio.name


@pytest.mark.asyncio
async def test_agent_crud_with_mcp_servers(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test CRUD operations with MCP server associations."""
    # Create MCP servers first
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.API)

    # Get the server IDs
    servers_dict = await storage.list_mcp_servers()
    server_ids = list(servers_dict.keys())
    assert len(server_ids) == 2

    # Test 1: Create agent with MCP server associations
    agent = Agent.model_validate(sample_agent.model_dump() | {"mcp_server_ids": server_ids})
    await storage.upsert_agent(sample_user_id, agent)

    # Verify the associations were created
    associated_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert len(associated_ids) == 2
    assert set(associated_ids) == set(server_ids)

    # Test 2: Update agent with different MCP server associations
    updated_agent = Agent.model_validate(agent.model_dump() | {"mcp_server_ids": [server_ids[0]]})
    await storage.upsert_agent(sample_user_id, updated_agent)

    # Verify the associations were updated
    updated_associated_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert len(updated_associated_ids) == 1
    assert updated_associated_ids == [server_ids[0]]

    # Test 3: Verify list_agents and get_agent populate MCP server information
    agents = await storage.list_agents(sample_user_id)
    assert len(agents) == 1
    retrieved_agent_list = agents[0]
    assert retrieved_agent_list.agent_id == agent.agent_id
    assert retrieved_agent_list.mcp_server_ids == [server_ids[0]]

    retrieved_agent_get = await storage.get_agent(sample_user_id, agent.agent_id)
    assert retrieved_agent_get.agent_id == agent.agent_id
    assert retrieved_agent_get.mcp_server_ids == [server_ids[0]]

    # Test 4: Delete agent and verify MCP server associations are cascaded
    await storage.delete_agent(sample_user_id, agent.agent_id)

    # Verify the association was cascaded (removed)
    empty_ids = await storage.get_agent_mcp_server_ids(agent.agent_id)
    assert empty_ids == []
