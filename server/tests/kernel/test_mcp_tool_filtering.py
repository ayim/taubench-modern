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
        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
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
        mock_agent.selected_tools.tool_names = []  # Empty list means no filtering
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server])
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
        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
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
        mock_agent.selected_tools.tool_names = [
            SelectedToolConfig(tool_name="tool1"),
            SelectedToolConfig(tool_name="tool3"),
        ]
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server])
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
        # Create mock MCP servers
        mcp_server1 = MCPServer(
            name="test-server-1",
            url="https://example1.com",
            transport="streamable-http",
        )
        mcp_server2 = MCPServer(
            name="test-server-2",
            url="https://example2.com",
            transport="streamable-http",
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
        mock_agent.selected_tools.tool_names = [
            SelectedToolConfig(tool_name="tool1"),
            SelectedToolConfig(tool_name="tool3"),
        ]  # Agent only allows these
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server1, mcp_server2])
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
        # Create mock MCP server
        mcp_server = MCPServer(
            name="test-server",
            url="https://example.com",
            transport="streamable-http",
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
        mock_agent.selected_tools.tool_names = []  # Empty list means no filtering
        mock_kernel = MagicMock()
        mock_kernel.agent = mock_agent
        tools_interface.attach_kernel(mock_kernel)

        # Call from_mcp_servers
        mcp_result = await tools_interface.from_mcp_servers([mcp_server])
        filtered_tools = mcp_result.tools
        issues = mcp_result.issues

        # Should return all tools (no filtering)
        assert len(filtered_tools) == 2
        assert filtered_tools[0].name == "tool1"
        assert filtered_tools[1].name == "tool2"
        assert issues == []
