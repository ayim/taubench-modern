"""Tests for MCP tool filtering functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.selected_tools import SelectedToolConfig
from agent_platform.core.tools.collected_tools import CollectedTools
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.server.kernel.tools import AgentServerToolsInterface


class TestMCPToolFiltering:
    """Test MCP tool filtering based on selected_tools."""

    @pytest.mark.asyncio
    async def test_no_agent_level_filtering_when_empty(self):
        """Test that no filtering occurs when agent selected_tools is empty."""
        from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
        )
        mcp_server_with_oauth = MCPServerWithOAuthConfig(
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            type=mcp_server.type,
            mcp_server_metadata=mcp_server.mcp_server_metadata,
            oauth_config=None,
        )

        # Create mock tools that would be returned
        all_tools = [
            ToolDefinition(name="tool1", description="Tool 1", input_schema={}),
            ToolDefinition(name="tool2", description="Tool 2", input_schema={}),
            ToolDefinition(name="tool3", description="Tool 3", input_schema={}),
        ]

        # Mock the tools interface with empty selected_tools
        tools_interface = AgentServerToolsInterface()
        tools_interface._cache = MagicMock()
        tools_interface._cache.get_or_fetch = AsyncMock(return_value=CollectedTools(tools=all_tools, issues=[]))

        # Mock kernel and agent with empty selected_tools
        mock_agent = MagicMock()
        mock_agent.selected_tools.tools = []  # Empty list means no filtering
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server_with_oauth])
        filtered_tools = mcp_result.tools
        issues = mcp_result.issues

        # Should return all tools (no filtering when selected_tools is empty)
        assert len(filtered_tools) == 3
        assert filtered_tools[0].name == "tool1"
        assert filtered_tools[1].name == "tool2"
        assert filtered_tools[2].name == "tool3"
        assert issues == []

    @pytest.mark.asyncio
    async def test_agent_level_filtering(self):
        """Test that agent-level selected_tools filtering works."""
        from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
        )
        mcp_server_with_oauth = MCPServerWithOAuthConfig(
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            type=mcp_server.type,
            mcp_server_metadata=mcp_server.mcp_server_metadata,
            oauth_config=None,
        )
        # Create mock tools that would be returned
        all_tools = [
            ToolDefinition(name="tool1", description="Tool 1", input_schema={}),
            ToolDefinition(name="tool2", description="Tool 2", input_schema={}),
            ToolDefinition(name="tool3", description="Tool 3", input_schema={}),
        ]

        # Mock the tools interface
        tools_interface = AgentServerToolsInterface()
        tools_interface._cache = MagicMock()
        tools_interface._cache.get_or_fetch = AsyncMock(return_value=CollectedTools(tools=all_tools, issues=[]))

        # Mock kernel and agent with specific selected_tools
        mock_agent = MagicMock()
        mock_agent.selected_tools.tools = [
            SelectedToolConfig(name="tool1"),
            SelectedToolConfig(name="tool3"),
        ]
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server_with_oauth])
        filtered_tools = mcp_result.tools
        issues = mcp_result.issues

        # Should only return tool1 and tool3
        assert len(filtered_tools) == 2
        assert filtered_tools[0].name == "tool1"
        assert filtered_tools[1].name == "tool3"
        assert issues == []

    @pytest.mark.asyncio
    async def test_agent_level_filtering_with_multiple_servers(self):
        """Test that agent-level filtering works across multiple servers."""
        from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

        # Create mock MCP servers
        mcp_server1 = MCPServer(
            name="test-server-1",
            url="https://example1.com",
            transport="streamable-http",
        )
        mcp_server_with_oauth1 = MCPServerWithOAuthConfig(
            name=mcp_server1.name,
            transport=mcp_server1.transport,
            url=mcp_server1.url,
            headers=mcp_server1.headers,
            command=mcp_server1.command,
            args=mcp_server1.args,
            env=mcp_server1.env,
            cwd=mcp_server1.cwd,
            force_serial_tool_calls=mcp_server1.force_serial_tool_calls,
            type=mcp_server1.type,
            mcp_server_metadata=mcp_server1.mcp_server_metadata,
            oauth_config=None,
        )
        mcp_server2 = MCPServer(
            name="test-server-2",
            url="https://example2.com",
            transport="streamable-http",
        )
        mcp_server_with_oauth2 = MCPServerWithOAuthConfig(
            name=mcp_server2.name,
            transport=mcp_server2.transport,
            url=mcp_server2.url,
            headers=mcp_server2.headers,
            command=mcp_server2.command,
            args=mcp_server2.args,
            env=mcp_server2.env,
            cwd=mcp_server2.cwd,
            force_serial_tool_calls=mcp_server2.force_serial_tool_calls,
            type=mcp_server2.type,
            mcp_server_metadata=mcp_server2.mcp_server_metadata,
            oauth_config=None,
        )

        # Create mock tools that would be returned from each server
        tools_from_server1 = [
            ToolDefinition(name="tool1", description="Tool 1", input_schema={}),
            ToolDefinition(name="tool2", description="Tool 2", input_schema={}),
        ]
        tools_from_server2 = [
            ToolDefinition(name="tool3", description="Tool 3", input_schema={}),
            ToolDefinition(name="tool4", description="Tool 4", input_schema={}),
        ]

        # Mock the tools interface
        tools_interface = AgentServerToolsInterface()
        tools_interface._cache = MagicMock()

        # Mock different responses for different servers
        async def mock_get_or_fetch(kind, key, fetch_coro):
            if "example1.com" in str(key):
                return CollectedTools(tools=tools_from_server1, issues=[])
            else:
                return CollectedTools(tools=tools_from_server2, issues=[])

        tools_interface._cache.get_or_fetch = mock_get_or_fetch

        # Mock kernel and agent with specific selected_tools
        mock_agent = MagicMock()
        mock_agent.selected_tools.tools = [
            SelectedToolConfig(name="tool1"),
            SelectedToolConfig(name="tool3"),
        ]  # Agent only allows these
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server_with_oauth1, mcp_server_with_oauth2])
        filtered_tools = mcp_result.tools
        issues = mcp_result.issues

        # Should only return tool1 and tool3 (agent-level filtering applied)
        assert len(filtered_tools) == 2
        tool_names = [tool.name for tool in filtered_tools]
        assert "tool1" in tool_names
        assert "tool3" in tool_names
        assert issues == []

    @pytest.mark.asyncio
    async def test_no_filtering_when_empty_lists(self):
        """Test that no filtering occurs when selected_tools lists are empty."""
        from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
        )
        mcp_server_with_oauth = MCPServerWithOAuthConfig(
            name=mcp_server.name,
            transport=mcp_server.transport,
            url=mcp_server.url,
            headers=mcp_server.headers,
            command=mcp_server.command,
            args=mcp_server.args,
            env=mcp_server.env,
            cwd=mcp_server.cwd,
            force_serial_tool_calls=mcp_server.force_serial_tool_calls,
            type=mcp_server.type,
            mcp_server_metadata=mcp_server.mcp_server_metadata,
            oauth_config=None,
        )
        # Create mock tools that would be returned
        all_tools = [
            ToolDefinition(name="tool1", description="Tool 1", input_schema={}),
            ToolDefinition(name="tool2", description="Tool 2", input_schema={}),
        ]

        # Mock the tools interface
        tools_interface = AgentServerToolsInterface()
        tools_interface._cache = MagicMock()
        tools_interface._cache.get_or_fetch = AsyncMock(return_value=CollectedTools(tools=all_tools, issues=[]))

        # Mock kernel and agent with empty selected_tools
        mock_agent = MagicMock()
        mock_agent.selected_tools.tools = []  # Empty list means no filtering
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server_with_oauth])
        filtered_tools = mcp_result.tools
        issues = mcp_result.issues

        # Should return all tools (no filtering)
        assert len(filtered_tools) == 2
        assert filtered_tools[0].name == "tool1"
        assert filtered_tools[1].name == "tool2"
        assert issues == []
