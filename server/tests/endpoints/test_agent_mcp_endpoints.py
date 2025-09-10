from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.core.user import User
from agent_platform.server.api.private_v2.agents import (
    create_agent,
    get_agent,
    list_agents,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat


@pytest.fixture
def mock_user():
    """Mock authenticated user for testing."""
    return User(user_id="test-user-123", sub="tenant:test-tenant:user:test-user")


@pytest.fixture
def mock_storage():
    """Mock storage dependency for testing."""
    storage = AsyncMock()
    storage.list_agents = AsyncMock()
    storage.get_agent = AsyncMock()
    storage.upsert_agent = AsyncMock()
    storage.create_mcp_server = AsyncMock()
    storage.list_mcp_servers = AsyncMock()
    storage.get_agent_mcp_server_ids = AsyncMock()
    storage.associate_mcp_servers_with_agent = AsyncMock()
    return storage


@pytest.fixture
def sample_agent():
    """Sample agent for testing."""
    from datetime import UTC, datetime

    from agent_platform.core.actions.action_package import ActionPackage
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.agent.observability_config import ObservabilityConfig
    from agent_platform.core.agent.question_group import QuestionGroup
    from agent_platform.core.runbook.runbook import Runbook
    from agent_platform.core.utils.secret_str import SecretString

    return Agent(
        user_id="test-user-123",
        agent_id=str(uuid4()),
        name="Test Agent",
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
        question_groups=[
            QuestionGroup(
                title="Test Question Group",
                questions=[
                    "Here's one question",
                    "Here's another question",
                ],
            ),
        ],
        observability_configs=[
            ObservabilityConfig(
                type="langsmith",
                api_key="test",
                api_url="https://api.langsmith.com",
                settings={"project_name": "test-project", "some_extra_setting": "some_extra_value"},
            ),
        ],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
        mcp_server_ids=[],
        mcp_servers=[],
    )


@pytest.fixture
def sample_mcp_server():
    """Sample MCP server for testing."""
    return MCPServer(
        name="test-mcp-server",
        transport="streamable-http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer test-token"},
    )


@pytest.mark.asyncio
async def test_agent_endpoints_with_mcp_server_ids(
    mock_user: User,
    mock_storage: AsyncMock,
    sample_agent: Agent,
    sample_mcp_server: MCPServer,
):
    """Test that agent endpoints properly handle MCP server IDs."""
    # Setup agent with MCP server IDs
    agent_with_mcp = sample_agent.copy(mcp_server_ids=["mcp-server-1", "mcp-server-2"])
    agent_without_mcp = sample_agent.copy(mcp_server_ids=[])

    # Test list_agents endpoint
    mock_storage.list_agents.return_value = [agent_with_mcp, agent_without_mcp]
    response = await list_agents(mock_user, mock_storage)
    assert len(response) == 2
    assert response[0].mcp_server_ids == ["mcp-server-1", "mcp-server-2"]
    assert response[1].mcp_server_ids == []

    # Test get_agent endpoint
    mock_storage.get_agent.return_value = agent_with_mcp
    response = await get_agent(mock_user, sample_agent.agent_id, mock_storage)
    assert response.mcp_server_ids == ["mcp-server-1", "mcp-server-2"]


@pytest.mark.asyncio
async def test_create_agent_with_mcp_server_ids(
    mock_user: User,
    mock_storage: AsyncMock,
    sample_agent: Agent,
    sample_mcp_server: MCPServer,
):
    """Test that create_agent endpoint properly handles MCP server IDs."""
    # Setup MCP servers in storage
    mock_storage.list_mcp_servers.return_value = {
        "mcp-server-1": sample_mcp_server,
        "mcp-server-2": sample_mcp_server.copy(),
    }

    # Setup agent with MCP server IDs
    agent_with_mcp = sample_agent.copy(mcp_server_ids=["mcp-server-1", "mcp-server-2"])
    mock_storage.upsert_agent.return_value = None
    mock_storage.get_agent.return_value = agent_with_mcp

    # Create payload with MCP server IDs
    payload = UpsertAgentPayload(
        name=sample_agent.name,
        description=sample_agent.description,
        version=sample_agent.version,
        user_id=sample_agent.user_id,
        platform_configs=[],
        agent_architecture=sample_agent.agent_architecture,
        action_packages=sample_agent.action_packages,
        mcp_server_ids=["mcp-server-1", "mcp-server-2"],
        mcp_servers=[],
        question_groups=sample_agent.question_groups,
        observability_configs=sample_agent.observability_configs,
        extra=sample_agent.extra,
        runbook=sample_agent.runbook_structured.raw_text,
    )

    # Call the endpoint
    response = await create_agent(payload, mock_user, mock_storage, None, None)

    # Verify the response includes MCP server IDs
    assert isinstance(response, AgentCompat)
    assert response.mcp_server_ids == ["mcp-server-1", "mcp-server-2"]


@pytest.mark.asyncio
async def test_agent_compat_with_mcp_server_ids(
    sample_agent: Agent,
    sample_mcp_server: MCPServer,
):
    """Test that AgentCompat.from_agent properly handles MCP server IDs and servers."""
    # Test with MCP server IDs only
    agent_with_ids = sample_agent.copy(mcp_server_ids=["mcp-server-1", "mcp-server-2"])
    agent_compat = AgentCompat.from_agent(agent_with_ids)
    assert agent_compat.mcp_server_ids == ["mcp-server-1", "mcp-server-2"]

    # Test with both MCP server IDs and MCP servers
    agent_with_both = sample_agent.copy(
        mcp_server_ids=["mcp-server-1", "mcp-server-2"], mcp_servers=[sample_mcp_server]
    )
    agent_compat = AgentCompat.from_agent(agent_with_both)
    assert agent_compat.mcp_server_ids == ["mcp-server-1", "mcp-server-2"]
    assert len(agent_compat.mcp_servers) == 1
    assert agent_compat.mcp_servers[0].name == sample_mcp_server.name
