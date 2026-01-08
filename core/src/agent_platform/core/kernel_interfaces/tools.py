from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from agent_platform.core.actions import ActionPackage
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.responses import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition, ToolExecutionResult

if TYPE_CHECKING:
    from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig
    from agent_platform.core.tools.collected_tools import CollectedTools

PendingToolCall = tuple[ToolDefinition, ResponseToolUseContent]


class ToolsInterface(ABC):
    """Manages building and execution of agent actions, internal tools,
    and CA-defined tools."""

    @abstractmethod
    def execute_pending_tool_calls(
        self,
        pending_tool_calls: list[PendingToolCall],
        message_to_update: ThreadMessageWithThreadState | None = None,
    ) -> AsyncGenerator[ToolExecutionResult, None]:
        """Executes tool calls from a model response.

        By default, this method will pass extra headers with the
        agent, user, and thread ID to the tool server.

        Arguments:
            pending_tool_calls: A list of pending tool calls to execute
            (a tuple of ToolDefinition and ResponseToolUseContent).

        Returns:
            A list of tool execution results.
        """

    @abstractmethod
    async def from_action_packages(self, action_packages: list[ActionPackage]) -> CollectedTools:
        """Converts a list of action packages into a list of tool definitions.

        Returns:
            A CollectedTools containing a list of tool definitions and a list of
            configuration issues.
        """

    @abstractmethod
    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServerWithOAuthConfig],
        use_caches: bool = True,
    ) -> CollectedTools:
        """Converts a list of MCP servers into a list of tool definitions.

        Returns:
            A CollectedTools containing a list of tool definitions and a list of
            configuration issues.
        """

    @abstractmethod
    async def load_mcp_servers(self) -> list[MCPServerWithOAuthConfig]:
        """Loads all the MCP servers from the storage and returns them as a list of MCPServerWithOAuthConfig."""
