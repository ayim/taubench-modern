import typing
from pathlib import Path

import pytest

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.server.api.private_v2.agents import create_agent, get_agent, list_agents
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage
    from server.tests.storage.sample_model_creator import SampleModelCreator


@pytest.mark.asyncio
async def test_agent_endpoints_with_mcp_server_ids(
    sqlite_storage: "SQLiteStorage",
    sqlite_model_creator: "SampleModelCreator",
    tmp_path: Path,
):
    """Test that agent endpoints properly handle MCP server IDs."""
    # Create MCP servers in storage
    mcp_server_1 = MCPServer(
        name="test-mcp-server-1",
        transport="streamable-http",
        url="https://example.com/mcp1",
        headers={"Authorization": "Bearer test-token-1"},
    )
    mcp_server_2 = MCPServer(
        name="test-mcp-server-2",
        transport="streamable-http",
        url="https://example.com/mcp2",
        headers={"Authorization": "Bearer test-token-2"},
    )

    server_id_1 = await sqlite_storage.create_mcp_server(mcp_server_1, MCPServerSource.API)
    server_id_2 = await sqlite_storage.create_mcp_server(mcp_server_2, MCPServerSource.API)

    # Use the provided SampleModelCreator fixture
    user = await sqlite_model_creator.get_authed_user()

    # Create agent with MCP server IDs
    agent_with_mcp = await sqlite_model_creator.obtain_sample_agent("Agent With MCP")
    await sqlite_storage.associate_mcp_servers_with_agent(agent_with_mcp.agent_id, [server_id_1, server_id_2])

    # Create agent without MCP server IDs (create directly since obtain_sample_agent caches)
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.actions.action_package import ActionPackage
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook.runbook import Runbook
    from agent_platform.core.utils.secret_str import SecretString

    agent_without_mcp = Agent(
        user_id=user.user_id,
        agent_id=str(uuid4()),
        name="Agent Without MCP",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-action-package",
                organization="test-organization",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=["action_1", "action_2"],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
            version="1.0.0",
        ),
        question_groups=[],
        observability_configs=[],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
        mcp_server_ids=[],
        mcp_servers=[],
    )
    await sqlite_storage.upsert_agent(user.user_id, agent_without_mcp)

    # Test list_agents endpoint
    response = await list_agents(user, sqlite_storage)
    assert len(response) >= 2

    # Find our agents in the response
    agent_with_mcp_response = next((a for a in response if a.agent_id == agent_with_mcp.agent_id), None)
    agent_without_mcp_response = next((a for a in response if a.agent_id == agent_without_mcp.agent_id), None)

    assert agent_with_mcp_response is not None
    assert agent_without_mcp_response is not None
    assert set(agent_with_mcp_response.mcp_server_ids) == {server_id_1, server_id_2}
    assert agent_without_mcp_response.mcp_server_ids == []

    # Test get_agent endpoint
    response = await get_agent(user, agent_with_mcp.agent_id, sqlite_storage)
    assert set(response.mcp_server_ids) == {server_id_1, server_id_2}


@pytest.mark.asyncio
async def test_create_agent_with_mcp_server_ids(
    sqlite_storage: "SQLiteStorage",
    sqlite_model_creator: "SampleModelCreator",
    tmp_path: Path,
):
    """Test that create_agent endpoint properly handles MCP server IDs."""
    # Create MCP servers in storage
    mcp_server_1 = MCPServer(
        name="test-mcp-server-1",
        transport="streamable-http",
        url="https://example.com/mcp1",
        headers={"Authorization": "Bearer test-token-1"},
    )
    mcp_server_2 = MCPServer(
        name="test-mcp-server-2",
        transport="streamable-http",
        url="https://example.com/mcp2",
        headers={"Authorization": "Bearer test-token-2"},
    )

    server_id_1 = await sqlite_storage.create_mcp_server(mcp_server_1, MCPServerSource.API)
    server_id_2 = await sqlite_storage.create_mcp_server(mcp_server_2, MCPServerSource.API)

    # Use the provided SampleModelCreator fixture
    user = await sqlite_model_creator.get_authed_user()
    sample_agent = await sqlite_model_creator.obtain_sample_agent("Test Agent")

    # Create payload with MCP server IDs
    payload = UpsertAgentPayload(
        name="New Agent With MCP",
        description=sample_agent.description,
        version=sample_agent.version,
        user_id=user.user_id,
        platform_configs=[],
        agent_architecture=sample_agent.agent_architecture,
        action_packages=sample_agent.action_packages,
        mcp_server_ids=[server_id_1, server_id_2],
        mcp_servers=[],
        question_groups=sample_agent.question_groups,
        observability_configs=sample_agent.observability_configs,
        extra=sample_agent.extra,
        runbook=sample_agent.runbook_structured.raw_text,
    )

    # Call the endpoint
    response = await create_agent(payload, user, sqlite_storage, None, None)

    # Verify the response includes MCP server IDs
    assert isinstance(response, AgentCompat)
    assert set(response.mcp_server_ids) == {server_id_1, server_id_2}


@pytest.mark.asyncio
async def test_agent_compat_with_mcp_server_ids(
    sqlite_storage: "SQLiteStorage",
    sqlite_model_creator: "SampleModelCreator",
    tmp_path: Path,
):
    """Test that AgentCompat.from_agent properly handles MCP server IDs and servers."""
    # Create MCP server in storage
    sample_mcp_server = MCPServer(
        name="test-mcp-server",
        transport="streamable-http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer test-token"},
    )

    server_id_1 = await sqlite_storage.create_mcp_server(sample_mcp_server, MCPServerSource.API)

    # Create another MCP server
    mcp_server_2 = MCPServer(
        name="test-mcp-server-2",
        transport="streamable-http",
        url="https://example.com/mcp2",
        headers={"Authorization": "Bearer test-token-2"},
    )
    server_id_2 = await sqlite_storage.create_mcp_server(mcp_server_2, MCPServerSource.API)

    # Use the provided SampleModelCreator fixture
    sample_agent = await sqlite_model_creator.obtain_sample_agent("Test Agent")

    # Test with MCP server IDs only
    agent_with_ids = sample_agent.copy(mcp_server_ids=[server_id_1, server_id_2])
    agent_compat = AgentCompat.from_agent(agent_with_ids)
    assert set(agent_compat.mcp_server_ids) == {server_id_1, server_id_2}

    # Test with both MCP server IDs and MCP servers
    agent_with_both = sample_agent.copy(mcp_server_ids=[server_id_1, server_id_2], mcp_servers=[sample_mcp_server])
    agent_compat = AgentCompat.from_agent(agent_with_both)
    assert set(agent_compat.mcp_server_ids) == {server_id_1, server_id_2}
    assert len(agent_compat.mcp_servers) == 1
    assert agent_compat.mcp_servers[0].name == sample_mcp_server.name
