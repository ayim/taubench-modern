from __future__ import annotations

import typing
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

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
async def sample_user_id(storage: SQLiteStorage) -> str:
    return await storage.get_system_user_id()


@pytest.mark.asyncio
async def test_agent_by_name(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    await storage.upsert_agent(sample_user_id, sample_agent)
    agent = await storage.get_agent_by_name(sample_user_id, sample_agent.name)
    assert agent is not None
    assert agent.agent_id == sample_agent.agent_id
    assert agent.name == sample_agent.name

    with pytest.raises(AgentNotFoundError):
        await storage.get_agent_by_name(sample_user_id, "Not Found")


@pytest.mark.asyncio
async def test_agent_crud_operations(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test Create, Read, Update, and Delete operations for agents."""
    # Create (via upsert)
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Read
    retrieved_agent = await storage.get_agent(sample_user_id, sample_agent.agent_id)
    assert retrieved_agent is not None
    assert retrieved_agent.agent_id == sample_agent.agent_id
    assert retrieved_agent.name == sample_agent.name

    # Update
    updated_agent = Agent.model_validate(
        sample_agent.model_dump() | {"name": "Updated Agent Name"},
    )
    await storage.upsert_agent(sample_user_id, updated_agent)
    retrieved_updated = await storage.get_agent(
        sample_user_id,
        sample_agent.agent_id,
    )
    assert retrieved_updated.name == "Updated Agent Name"

    # Patch
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

    # Delete
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)
    with pytest.raises(AgentNotFoundError):
        await storage.get_agent(sample_user_id, sample_agent.agent_id)


@pytest.mark.asyncio
async def test_update_agent_prop_not_name(
    storage: SQLiteStorage | PostgresStorage,
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
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """
    Test that listing all agents (across all users) returns agents from different users.
    """
    # Create an agent for the original user
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create a second user and an agent for that user
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
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test listing agents for a user."""
    await storage.upsert_agent(sample_user_id, sample_agent)
    agents = await storage.list_agents(sample_user_id)
    assert len(agents) == 1
    assert agents[0].agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_agent_system_user_access(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
) -> None:
    """Test system user's ability to access other users' resources."""
    regular_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:regular_user",
    )
    await storage.upsert_agent(regular_user.user_id, sample_agent)
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
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test regular user's ability to access their own resources."""
    this_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:this_user",
    )
    await storage.upsert_agent(this_user.user_id, sample_agent)
    regular_accessed_agent = await storage.get_agent(
        this_user.user_id,
        sample_agent.agent_id,
    )
    assert regular_accessed_agent is not None
    assert regular_accessed_agent.agent_id == sample_agent.agent_id

    other_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:other_user",
    )
    with pytest.raises(UserAccessDeniedError):
        await storage.get_agent(other_user.user_id, sample_agent.agent_id)


@pytest.mark.asyncio
async def test_agent_delete_cascades_threads(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that deleting an agent cascades to deletion of its associated threads.
    """
    # Create an agent and a thread for that agent.
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    # Verify the thread exists.
    existing_thread = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert existing_thread is not None

    # Delete the agent.
    await storage.delete_agent(sample_user_id, sample_agent.agent_id)

    # Because threads reference the agent (via a foreign key with cascade),
    # trying to retrieve the thread should now result in a not-found error.
    with pytest.raises(ThreadNotFoundError):
        await storage.get_thread(sample_user_id, sample_thread.thread_id)


@pytest.mark.asyncio
async def test_agent_duplicate_name_constraint(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """
    Test that creating two agents with the same name (ignoring case)
    for the same user violates the uniqueness constraint.
    """
    # Create the first agent with name "Test Agent"
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Create a second agent with the same name (different case) and a new agent_id.
    duplicate_agent = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "test agent"},
    )
    with pytest.raises(AgentWithNameAlreadyExistsError):
        await storage.upsert_agent(sample_user_id, duplicate_agent)


@pytest.mark.asyncio
async def test_agent_case_insensitive_lookup(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """
    Test that retrieving an agent by name is case-insensitive.
    """
    await storage.upsert_agent(sample_user_id, sample_agent)
    # Lookup using lower-case and upper-case variations.
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
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """
    Test that attempting to insert an agent with invalid JSON metadata
    (for example, a value that cannot be serialized) raises an error.
    """
    # In Python, trying to serialize an unserializable object (like a set)
    # should raise a TypeError before even reaching the database or,
    # if not caught, lead to a DB integrity error.
    invalid_agent = Agent.model_validate(
        sample_agent.model_dump() | {"extra": {"invalid": set([1, 2, 3])}},
    )
    with pytest.raises((TypeError, ValueError)):
        await storage.upsert_agent(sample_user_id, invalid_agent)


@pytest.mark.asyncio
async def test_agent_filter_by_user(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
) -> None:
    """
    Test that listing agents for a specific user returns only agents for that user.
    """
    # Create an agent for user A.
    user_a, _ = await storage.get_or_create_user(sub="tenant:testing:user:user_a")
    agent_a = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "User A Agent", "user_id": user_a.user_id},
    )
    await storage.upsert_agent(user_a.user_id, agent_a)

    # Create an agent for user B.
    user_b, _ = await storage.get_or_create_user(sub="tenant:testing:user:user_b")
    agent_b = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "User B Agent", "user_id": user_b.user_id},
    )
    await storage.upsert_agent(user_b.user_id, agent_b)

    # List agents for user A only.
    agents_a = await storage.list_agents(user_a.user_id)
    agent_ids_a = {agent.agent_id for agent in agents_a}
    assert agent_a.agent_id in agent_ids_a
    # Ensure that user B's agent is not returned.
    assert agent_b.agent_id not in agent_ids_a


@pytest.mark.asyncio
async def test_agent_mcp_server_operations(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test MCP server operations including association, retrieval, updates, and population."""
    # Create MCP servers first
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.API)

    # Get the server IDs
    servers_dict = await storage.list_mcp_servers()
    server_ids = list(servers_dict.keys())
    assert len(server_ids) == 2

    # Test 1: Basic MCP server operations (association, retrieval, updates)
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

    # Test 2: MCP server population from different sources
    # Agent with join table associations only
    agent_join = Agent.model_validate(sample_agent.model_dump() | {"mcp_server_ids": [server_ids[1]]})
    await storage.upsert_agent(sample_user_id, agent_join)
    await storage.associate_mcp_servers_with_agent(agent_join.agent_id, [server_ids[1]])

    populated_agent_join = await storage._populate_agent_mcp_servers(agent_join)
    assert populated_agent_join.mcp_server_ids == [server_ids[1]]
    assert populated_agent_join.mcp_servers == []

    # Agent with JSON-based MCP servers only
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

    # Agent with both join table and JSON-based servers
    agent_both = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Both Agent",
            "mcp_server_ids": [server_ids[0]],
            "mcp_servers": [sample_mcp_server_http.model_dump()],
        }
    )
    await storage.upsert_agent(sample_user_id, agent_both)
    await storage.associate_mcp_servers_with_agent(agent_both.agent_id, [server_ids[0]])

    populated_agent_both = await storage._populate_agent_mcp_servers(agent_both)
    assert populated_agent_both.mcp_server_ids == [server_ids[0]]
    assert len(populated_agent_both.mcp_servers) == 1
    assert populated_agent_both.mcp_servers[0].name == sample_mcp_server_http.name

    # Test 3: Edge case - agent without MCP servers
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
async def test_agent_crud_with_mcp_servers(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test CRUD operations with MCP server associations and cascading behavior."""
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


@pytest.mark.asyncio
async def test_agent_platform_params_association(
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test platform params association without validation."""
    from agent_platform.core.platforms.openai import OpenAIPlatformParameters
    from agent_platform.core.utils import SecretString

    # Create two valid platform params entries
    platform_params_1 = OpenAIPlatformParameters(
        name="Test OpenAI Platform 1",
        openai_api_key=SecretString("sk-test-key-1"),
        models={"openai": ["gpt-4o"]},
        platform_id=str(uuid4()),
    )
    await storage.create_platform_params(platform_params_1)

    platform_params_2 = OpenAIPlatformParameters(
        name="Test OpenAI Platform 2",
        openai_api_key=SecretString("sk-test-key-2"),
        models={"openai": ["gpt-3.5-turbo"]},
        platform_id=str(uuid4()),
    )
    await storage.create_platform_params(platform_params_2)

    platform_id_1 = platform_params_1.platform_id
    platform_id_2 = platform_params_2.platform_id

    # Create agent
    agent = Agent.model_validate(sample_agent.model_dump() | {"platform_params_ids": []})
    await storage.upsert_agent(sample_user_id, agent)

    # Test 1: Associate with single platform_params_id
    await storage.associate_platform_params_with_agent(agent.agent_id, [platform_id_1])

    # Verify the association exists
    associated_ids = await storage.get_agent_platform_params_ids(agent.agent_id)
    assert len(associated_ids) == 1
    assert associated_ids[0] == platform_id_1

    # Test 2: Associate with multiple platform_params_ids (should replace existing)
    await storage.associate_platform_params_with_agent(agent.agent_id, [platform_id_1, platform_id_2])

    # Verify both associations exist
    associated_ids_after_multiple = await storage.get_agent_platform_params_ids(agent.agent_id)
    assert len(associated_ids_after_multiple) == 2
    assert platform_id_1 in associated_ids_after_multiple
    assert platform_id_2 in associated_ids_after_multiple

    # Test 3: Associate with empty list (should remove all associations)
    await storage.associate_platform_params_with_agent(agent.agent_id, [])

    # Verify no associations exist
    final_associated_ids = await storage.get_agent_platform_params_ids(agent.agent_id)
    assert len(final_associated_ids) == 0


@pytest.mark.asyncio
async def test_delete_agent_other_user(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
) -> None:
    owner, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    agent = Agent.model_validate(sample_agent.model_dump() | {"user_id": owner.user_id})
    await storage.upsert_agent(owner.user_id, agent)

    other_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:other")
    with pytest.raises(UserAccessDeniedError):
        await storage.delete_agent(other_user.user_id, agent.agent_id)


@pytest.mark.asyncio
async def test_patch_agent(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
) -> None:
    owner, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    agent = Agent.model_validate(sample_agent.model_dump() | {"user_id": owner.user_id})
    await storage.upsert_agent(owner.user_id, agent)

    # Test that a non-existent agent cannot be patched
    with pytest.raises(AgentNotFoundError):
        await storage.patch_agent(owner.user_id, str(uuid4()), "Some Name", "Some Description")

    # Test that other users cannot patch the agent
    other_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:other")
    with pytest.raises(UserAccessDeniedError):
        await storage.patch_agent(other_user.user_id, agent.agent_id, "Hacked Name", "Hacked Description")

    # Test that a patch cannot occur if the name is the same
    dup_agent = Agent.model_validate(
        agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Unrelated Agent",
            "description": "Unrelated Description",
        }
    )
    await storage.upsert_agent(owner.user_id, dup_agent)
    with pytest.raises(AgentWithNameAlreadyExistsError):
        await storage.patch_agent(owner.user_id, agent.agent_id, dup_agent.name, dup_agent.description)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_sub", "caller_sub", "expect_error"),
    [
        ("tenant:testing:user:owner", "tenant:testing:user:other", True),
        ("tenant:testing:system:system_user", "tenant:testing:user:other", False),
        ("tenant:testing:user:owner", "tenant:testing:system:system_user", False),
        ("tenant:testing:user:owner", "tenant:testing:user:system_user", False),
        ("tenant:testing:user:system_user", "tenant:testing:user:other", False),
    ],
)
async def test_agent_access_control_users(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
    owner_sub: str,
    caller_sub: str,
    expect_error: bool,
) -> None:
    """Test CRUD operations for agents with access control."""
    # Create explicit owner user and other user
    owner_user, _ = await storage.get_or_create_user(sub=owner_sub)
    other_user, _ = await storage.get_or_create_user(sub=caller_sub)
    agent_owned = Agent.model_validate(sample_agent.model_dump() | {"user_id": owner_user.user_id})

    # Create (via upsert)
    await storage.upsert_agent(owner_user.user_id, agent_owned)

    # Read
    if expect_error:
        with pytest.raises(UserAccessDeniedError):
            await storage.get_agent(other_user.user_id, agent_owned.agent_id)
    else:
        retrieved_agent = await storage.get_agent(other_user.user_id, agent_owned.agent_id)
        assert retrieved_agent is not None
        assert retrieved_agent.agent_id == agent_owned.agent_id
        assert retrieved_agent.name == agent_owned.name

    # Update
    updated_agent = Agent.model_validate(
        agent_owned.model_dump() | {"name": "Updated Agent Name"},
    )
    if expect_error:
        with pytest.raises(UserAccessDeniedError):
            await storage.upsert_agent(other_user.user_id, updated_agent)
    else:
        await storage.upsert_agent(other_user.user_id, updated_agent)
        retrieved_updated = await storage.get_agent(
            other_user.user_id,
            agent_owned.agent_id,
        )
        assert retrieved_updated.name == "Updated Agent Name"

    # Patch
    if expect_error:
        with pytest.raises(UserAccessDeniedError):
            await storage.patch_agent(
                other_user.user_id,
                agent_owned.agent_id,
                "Updated Agent Name (Patch)",
                "Updated Agent Description (Patch)",
            )
    else:
        await storage.patch_agent(
            other_user.user_id,
            agent_owned.agent_id,
            "Updated Agent Name (Patch)",
            "Updated Agent Description (Patch)",
        )
        retrieved_updated = await storage.get_agent(
            other_user.user_id,
            agent_owned.agent_id,
        )
        assert retrieved_updated.name == "Updated Agent Name (Patch)"
        assert retrieved_updated.description == "Updated Agent Description (Patch)"

    # Delete by other user should be denied
    if expect_error:
        with pytest.raises(UserAccessDeniedError):
            await storage.delete_agent(other_user.user_id, agent_owned.agent_id)
    else:
        await storage.delete_agent(other_user.user_id, agent_owned.agent_id)
        with pytest.raises(AgentNotFoundError):
            await storage.get_agent(owner_user.user_id, agent_owned.agent_id)
