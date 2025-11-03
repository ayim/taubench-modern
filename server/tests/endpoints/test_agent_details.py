from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from agent_platform.core.actions.action_package import ActionPackage, SecretString
from agent_platform.core.agent import Agent, AgentArchitecture, AgentUserInterface
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.runbook import Runbook
from agent_platform.core.user import User
from agent_platform.server.api.private_v2.agents import (
    get_agent_details,
    get_agent_user_interfaces,
)


@pytest.fixture
def mock_user():
    """Mock authenticated user for testing."""
    return User(user_id="test-user-123", sub="tenant:test-tenant:user:test-user")


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    # Mock methods that are called by _process_mcp_servers
    storage.get_mcp_servers_by_ids.return_value = {}  # Return empty dict by default
    storage.get_dids_connection_details.return_value = None  # Return None by default
    return storage


def create_test_agent(action_packages=None, mcp_servers=None):
    """Helper function to create a test agent with given action packages and MCP servers."""
    return Agent(
        name="Test Agent",
        description="Test Description",
        user_id="test_user",
        version="1.0.0",
        action_packages=action_packages or [],
        mcp_servers=mcp_servers or [],
        runbook_structured=Runbook(raw_text="test runbook", content=[]),
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
    )


async def test_agent_details_no_action_packages(mock_user, mock_storage):
    """Test getting agent details for an agent with no action packages."""
    agent = create_test_agent()
    mock_storage.get_agent.return_value = agent

    result = await get_agent_details(
        user=mock_user,
        aid="test_agent",
        storage=mock_storage,
    )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 0


async def test_agent_details_one_action_package_online(mock_user, mock_storage):
    """Test getting agent details for an agent with one online action package."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    # Mock the action packages data response with new structure
    mock_response_data = {"TestServerPackage": {"actions": ["Test Action"], "version": "1.0.0"}}

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data"
    ) as mock_fetch:
        mock_fetch.return_value = mock_response_data

        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "TestServerPackage"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1
    assert result.action_packages[0].actions[0].name == "Test Action"


async def test_agent_details_one_action_package_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with one offline action package."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        side_effect=Exception("Failed to fetch action packages"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "test_package"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "offline"
    assert len(result.action_packages[0].actions) == 0


async def test_agent_details_two_action_packages_both_online(mock_user, mock_storage):
    """Test getting agent details for an agent with two online action packages."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString("test_key"),
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages)

    # Mock response with two server packages
    mock_response_data = {
        "ServerPackageA": {"actions": ["action_a"], "version": "1.0.0"},
        "ServerPackageB": {"actions": ["action_b"], "version": "1.0.0"},
    }

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        return_value=mock_response_data,
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2  # Two server packages

    # Should get server package names, not agent package names
    package_names = [pkg.name for pkg in result.action_packages]
    assert "ServerPackageA" in package_names
    assert "ServerPackageB" in package_names

    for package in result.action_packages:
        assert package.version == "1.0.0"
        assert package.status == "online"
        assert len(package.actions) == 1


async def test_agent_details_two_action_packages_both_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with two offline action packages."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString("test_key"),
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages)

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        side_effect=Exception("Failed to fetch action packages"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2
    for i, package in enumerate(result.action_packages):
        assert package.name == f"test_package_{i}"  # Agent package names for offline packages
        assert package.version == "1.0.0"
        assert package.status == "offline"
        assert len(package.actions) == 0


async def test_agent_details_two_action_packages_mixed_status(mock_user, mock_storage):
    """Test getting agent details for an agent with one online and one offline action package."""
    action_packages = [
        ActionPackage(
            name="online_package",
            organization="test_org",
            version="1.0.0",
            url="http://online-server.com",
            api_key=SecretString("test_key_online"),
        ),
        ActionPackage(
            name="offline_package",
            organization="test_org",
            version="1.0.0",
            url="http://offline-server.com",
            api_key=SecretString("test_key_offline"),
        ),
    ]
    agent = create_test_agent(action_packages=action_packages)

    async def mock_fetch_action_packages_data(url, api_key):
        # Only succeed for the online server
        if url == "http://online-server.com":
            return {"OnlineServerPackage": {"actions": ["online_action"], "version": "1.0.0"}}
        else:
            raise Exception("Server offline")

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        side_effect=mock_fetch_action_packages_data,
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2

    # Sort by status to ensure consistent ordering
    packages_by_status = {}
    for pkg in result.action_packages:
        packages_by_status[pkg.status] = pkg

    # Online package should have server name
    online_pkg = packages_by_status["online"]
    assert online_pkg.name == "OnlineServerPackage"
    assert online_pkg.version == "1.0.0"
    assert online_pkg.status == "online"
    assert len(online_pkg.actions) == 1

    # Offline package should have agent name
    offline_pkg = packages_by_status["offline"]
    assert offline_pkg.name == "offline_package"
    assert offline_pkg.version == "1.0.0"
    assert offline_pkg.status == "offline"
    assert len(offline_pkg.actions) == 0


# =============================================================================
# MCP SERVER TESTS
# =============================================================================


async def test_agent_details_no_mcp_servers(mock_user, mock_storage):
    """Test getting agent details for an agent with no MCP servers."""
    agent = create_test_agent()
    mock_storage.get_agent.return_value = agent

    result = await get_agent_details(
        user=mock_user,
        aid="test_agent",
        storage=mock_storage,
    )

    assert result.runbook == "test runbook"
    assert len(result.mcp_servers) == 0


async def test_agent_details_one_mcp_server_online(mock_user, mock_storage):
    """Test getting agent details for an agent with one online MCP server."""
    mcp_server = MCPServer(
        name="test_mcp_server",
        url="http://test-mcp.com",
    )
    agent = create_test_agent(mcp_servers=[mcp_server])

    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        return_value=[AsyncMock(name="test_mcp_action")],
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "test_mcp_server"
    assert result.mcp_servers[0].status == "online"
    assert len(result.mcp_servers[0].actions) == 1


async def test_agent_details_one_mcp_server_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with one offline MCP server."""
    mcp_server = MCPServer(
        name="test_mcp_server",
        url="http://test-mcp.com",
    )
    agent = create_test_agent(mcp_servers=[mcp_server])

    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        side_effect=Exception("Failed to get MCP tool definitions"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "test_mcp_server"
    assert result.mcp_servers[0].status == "offline"
    assert len(result.mcp_servers[0].actions) == 0


async def test_agent_details_two_mcp_servers_both_online(mock_user, mock_storage):
    """Test getting agent details for an agent with two online MCP servers."""
    mcp_servers = [
        MCPServer(
            name=f"test_mcp_server_{i}",
            url="http://test-mcp.com",
        )
        for i in range(2)
    ]
    agent = create_test_agent(mcp_servers=mcp_servers)

    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        return_value=[AsyncMock(name="test_mcp_action")],
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.mcp_servers) == 2
    for i, server in enumerate(result.mcp_servers):
        assert server.name == f"test_mcp_server_{i}"
        assert server.status == "online"
        assert len(server.actions) == 1


async def test_agent_details_two_mcp_servers_both_offline(mock_user, mock_storage):
    """Test getting agent details for an agent with two offline MCP servers."""
    mcp_servers = [
        MCPServer(
            name=f"test_mcp_server_{i}",
            url="http://test-mcp.com",
        )
        for i in range(2)
    ]
    agent = create_test_agent(mcp_servers=mcp_servers)

    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        side_effect=Exception("Failed to get MCP tool definitions"),
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.mcp_servers) == 2
    for i, server in enumerate(result.mcp_servers):
        assert server.name == f"test_mcp_server_{i}"
        assert server.status == "offline"
        assert len(server.actions) == 0


async def test_agent_details_two_mcp_servers_mixed_status(mock_user, mock_storage):
    """Test getting agent details for an agent with mixed online/offline MCP servers."""
    # Create one MCP server that will be "online" and one that will be "offline"
    online_mcp_server = MCPServer(
        name="test_mcp_server_online",
        url="http://test-mcp-online.com",
    )
    offline_mcp_server = MCPServer(
        name="test_mcp_server_offline",
        url="http://test-mcp-offline.com",
    )

    # Create separate agents to test online and offline scenarios
    online_agent = create_test_agent(mcp_servers=[online_mcp_server])
    offline_agent = create_test_agent(mcp_servers=[offline_mcp_server])

    # Test online server first
    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        return_value=[AsyncMock(name="test_mcp_action")],
    ):
        mock_storage.get_agent.return_value = online_agent
        online_result = await get_agent_details(
            user=mock_user,
            aid="test_agent_online",
            storage=mock_storage,
        )

    # Test offline server
    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        side_effect=Exception("Failed to get MCP tool definitions"),
    ):
        mock_storage.get_agent.return_value = offline_agent
        offline_result = await get_agent_details(
            user=mock_user,
            aid="test_agent_offline",
            storage=mock_storage,
        )

    # Verify online server
    assert online_result.runbook == "test runbook"
    assert len(online_result.mcp_servers) == 1
    assert online_result.mcp_servers[0].name == "test_mcp_server_online"
    assert online_result.mcp_servers[0].status == "online"
    assert len(online_result.mcp_servers[0].actions) == 1

    # Verify offline server
    assert offline_result.runbook == "test runbook"
    assert len(offline_result.mcp_servers) == 1
    assert offline_result.mcp_servers[0].name == "test_mcp_server_offline"
    assert offline_result.mcp_servers[0].status == "offline"
    assert len(offline_result.mcp_servers[0].actions) == 0


# =============================================================================
# COMBINED ACTION PACKAGE AND MCP SERVER TESTS
# =============================================================================


async def test_agent_details_with_action_packages_and_mcp_servers_all_online(
    mock_user, mock_storage
):
    """Test getting agent details for an agent with both action packages and MCP servers,
    all online."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    mcp_server = MCPServer(
        name="test_mcp_server",
        url="http://test-mcp.com",
    )
    agent = create_test_agent(action_packages=[action_package], mcp_servers=[mcp_server])

    # Mock action packages response
    mock_action_packages_data = {
        "TestServerPackage": {"actions": ["Test Action"], "version": "1.0.0"}
    }

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        return_value=mock_action_packages_data,
    ):
        with patch(
            "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
            return_value=[AsyncMock(name="test_mcp_action")],
        ):
            mock_storage.get_agent.return_value = agent
            result = await get_agent_details(
                user=mock_user,
                aid="test_agent",
                storage=mock_storage,
            )

    assert result.runbook == "test runbook"

    # Verify action package
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "TestServerPackage"
    assert result.action_packages[0].version == "1.0.0"
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1

    # Verify MCP server
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "test_mcp_server"
    assert result.mcp_servers[0].status == "online"
    assert len(result.mcp_servers[0].actions) == 1


async def test_agent_details_with_action_packages_and_mcp_servers_mixed_status(
    mock_user, mock_storage
):
    """Test getting agent details for an agent with both action packages and MCP servers,
    mixed status."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    mcp_server = MCPServer(
        name="test_mcp_server",
        url="http://test-mcp.com",
    )
    agent = create_test_agent(action_packages=[action_package], mcp_servers=[mcp_server])

    # Mock action packages response (online)
    mock_action_packages_data = {
        "TestServerPackage": {"actions": ["Test Action"], "version": "1.0.0"}
    }

    # Action package online, MCP server offline
    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        return_value=mock_action_packages_data,
    ):
        with patch(
            "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
            side_effect=Exception("Failed to get MCP tool definitions"),
        ):
            mock_storage.get_agent.return_value = agent
            result = await get_agent_details(
                user=mock_user,
                aid="test_agent",
                storage=mock_storage,
            )

    assert result.runbook == "test runbook"

    # Verify action package (online)
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "TestServerPackage"
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1

    # Verify MCP server (offline)
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "test_mcp_server"
    assert result.mcp_servers[0].status == "offline"
    assert len(result.mcp_servers[0].actions) == 0


async def test_agent_details_with_multiple_action_packages_and_mcp_servers(mock_user, mock_storage):
    """Test getting agent details for an agent with multiple action packages and MCP servers."""
    action_packages = [
        ActionPackage(
            name=f"test_package_{i}",
            organization="test_org",
            version="1.0.0",
            url="http://test.com",
            api_key=SecretString(f"test_key_{i}"),
        )
        for i in range(2)
    ]
    mcp_servers = [
        MCPServer(
            name=f"test_mcp_server_{i}",
            url=f"http://test-mcp-{i}.com",
        )
        for i in range(2)
    ]
    agent = create_test_agent(action_packages=action_packages, mcp_servers=mcp_servers)

    # Mock action packages response (both agent packages point to same URL, so get server packages)
    mock_action_packages_data = {
        "ServerPackageA": {"actions": ["action_a"], "version": "1.0.0"},
        "ServerPackageB": {"actions": ["action_b"], "version": "1.0.0"},
    }

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        return_value=mock_action_packages_data,
    ):
        with patch(
            "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
            return_value=[AsyncMock(name="test_mcp_action")],
        ):
            mock_storage.get_agent.return_value = agent
            result = await get_agent_details(
                user=mock_user,
                aid="test_agent",
                storage=mock_storage,
            )

    assert result.runbook == "test runbook"

    # Verify action packages
    assert len(result.action_packages) == 2
    package_names = [pkg.name for pkg in result.action_packages]
    assert "ServerPackageA" in package_names
    assert "ServerPackageB" in package_names

    for package in result.action_packages:
        assert package.status == "online"
        assert len(package.actions) == 1

    # Verify MCP servers
    assert len(result.mcp_servers) == 2
    for i, server in enumerate(result.mcp_servers):
        assert server.name == f"test_mcp_server_{i}"
        assert server.status == "online"
        assert len(server.actions) == 1


async def test_agent_details_with_global_and_agent_specific_mcp_servers(mock_user, mock_storage):
    """
    Test getting agent details for an agent with both
    global MCP servers (from storage) and agent-specific MCP servers.
    """
    # Create global MCP servers that will be returned by storage
    global_mcp_server = MCPServer(
        name="global_mcp_server",
        url="http://global-mcp.com",
    )

    # Create agent-specific MCP server
    agent_mcp_server = MCPServer(
        name="agent_specific_mcp_server",
        url="http://agent-mcp.com",
    )

    # Create agent with agent-specific MCP server and some global MCP server IDs
    agent = create_test_agent(mcp_servers=[agent_mcp_server])
    agent = agent.copy(mcp_server_ids=["global-server-id-123"])

    # Mock storage to return global MCP server
    mock_storage.get_agent.return_value = agent
    mock_storage.get_mcp_servers_by_ids.return_value = {"global-server-id-123": global_mcp_server}

    # Create a proper mock tool definition with name attribute
    mock_tool_def = AsyncMock()
    mock_tool_def.name = "test_mcp_action"

    with patch(
        "agent_platform.core.mcp.mcp_server.MCPServer.to_tool_definitions",
        return_value=[mock_tool_def],
    ):
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"

    # Verify we have both global and agent-specific MCP servers
    assert len(result.mcp_servers) == 2

    server_names = [server.name for server in result.mcp_servers]
    assert "global_mcp_server" in server_names
    assert "agent_specific_mcp_server" in server_names


# ============================================================================
# Tests for version override functionality
# ============================================================================


async def test_agent_details_with_version_override(mock_user, mock_storage):
    """Test that version information is properly overridden from /api/actionPackages."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    # Mock response with version override (from /api/actionPackages)
    mock_response_data = {
        "TestServerPackage": {
            "actions": ["Test Action"],
            "version": "2.5.0",  # This should override the default "1.0.0"
        }
    }

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data"
    ) as mock_fetch:
        mock_fetch.return_value = mock_response_data

        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "TestServerPackage"
    assert result.action_packages[0].version == "2.5.0"  # Should be overridden
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1
    assert result.action_packages[0].actions[0].name == "Test Action"


async def test_agent_details_with_default_version_fallback(mock_user, mock_storage):
    """Test that default version is used when /api/actionPackages is not available."""
    action_package = ActionPackage(
        name="test_package",
        organization="test_org",
        version="1.0.0",
        url="http://test.com",
        api_key=SecretString("test_key"),
    )
    agent = create_test_agent(action_packages=[action_package])

    # Mock response with default version (from /api/actionPackages)
    mock_response_data = {
        "TestServerPackage": {
            "actions": ["Test Action"],
            "version": "1.0.0",  # Default version from /api/actionPackages
        }
    }

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data"
    ) as mock_fetch:
        mock_fetch.return_value = mock_response_data

        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 1
    assert result.action_packages[0].name == "TestServerPackage"
    assert result.action_packages[0].version == "1.0.0"  # Default version
    assert result.action_packages[0].status == "online"
    assert len(result.action_packages[0].actions) == 1
    assert result.action_packages[0].actions[0].name == "Test Action"


async def test_agent_details_multiple_packages_with_mixed_versions(mock_user, mock_storage):
    """Test agent details with multiple packages having different versions."""
    action_packages = [
        ActionPackage(
            name="package_a",
            organization="test_org",
            version="1.0.0",
            url="http://test-a.com",
            api_key=SecretString("test_key"),
        ),
        ActionPackage(
            name="package_b",
            organization="test_org",
            version="1.0.0",
            url="http://test-b.com",
            api_key=SecretString("test_key"),
        ),
    ]
    agent = create_test_agent(action_packages=action_packages)

    async def mock_fetch_action_packages_data(url, api_key):
        # Return different data based on URL to simulate different servers
        if "test-a.com" in url:
            return {"Package A": {"actions": ["Action A1", "Action A2"], "version": "3.2.1"}}
        elif "test-b.com" in url:
            return {"Package B": {"actions": ["Action B1"], "version": "1.0.0"}}
        else:
            return {}

    with patch(
        "agent_platform.server.api.private_v2.agents._fetch_action_packages_data",
        side_effect=mock_fetch_action_packages_data,
    ):
        mock_storage.get_agent.return_value = agent
        result = await get_agent_details(
            user=mock_user,
            aid="test_agent",
            storage=mock_storage,
        )

    assert result.runbook == "test runbook"
    assert len(result.action_packages) == 2

    # Find packages by name
    package_a = next(pkg for pkg in result.action_packages if pkg.name == "Package A")
    package_b = next(pkg for pkg in result.action_packages if pkg.name == "Package B")

    # Verify Package A has overridden version
    assert package_a.version == "3.2.1"
    assert package_a.status == "online"
    assert len(package_a.actions) == 2
    assert package_a.actions[0].name == "Action A1"
    assert package_a.actions[1].name == "Action A2"

    # Verify Package B has default version
    assert package_b.version == "1.0.0"
    assert package_b.status == "online"
    assert len(package_b.actions) == 1
    assert package_b.actions[0].name == "Action B1"


# ============================================================================
# Tests for helper functions
# ============================================================================


# Note: HTTP integration tests for _fetch_action_packages_data are complex to mock
# due to async context managers. The core functionality is tested through the
# endpoint tests above, which mock the _fetch_action_packages_data function directly.


# ============================================================================
# Tests for user interfaces endpoint
# ============================================================================


async def test_get_agent_user_interfaces_empty(mock_user, mock_storage):
    """Test agent with no user interfaces returns empty list."""
    agent = create_test_agent()
    mock_storage.get_agent.return_value = agent

    result = await get_agent_user_interfaces(
        agent_id="test_agent", user=mock_user, storage=mock_storage
    )

    assert result == []


async def test_get_agent_user_interfaces(mock_user, mock_storage):
    """Test agent with valid user interface."""
    agent = create_test_agent()
    agent = agent.copy(
        extra={
            "agent_settings": {
                "user_interfaces": [
                    AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY,
                    "unknown-interface",
                ]
            }
        }
    )
    mock_storage.get_agent.return_value = agent

    result = await get_agent_user_interfaces(
        agent_id="test_agent", user=mock_user, storage=mock_storage
    )

    assert len(result) == 1
    assert result[0] == AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY


async def test_get_agent_user_interfaces_not_found(mock_user, mock_storage):
    """Test 404 when agent not found."""
    mock_storage.get_agent.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_agent_user_interfaces(
            agent_id="nonexistent", user=mock_user, storage=mock_storage
        )

    assert exc_info.value.status_code == 404
