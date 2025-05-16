from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from agent_platform.core.actions import ActionPackage
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.mcp import MCPServer
from agent_platform.core.responses import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition, ToolExecutionResult

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

        Arguments:
            pending_tool_calls: A list of pending tool calls to execute
            (a tuple of ToolDefinition and ResponseToolUseContent).

        Returns:
            A list of tool execution results.
        """
        pass

    @abstractmethod
    async def from_action_packages(
        self, action_packages: list[ActionPackage], additional_headers: dict | None
    ) -> tuple[list[ToolDefinition], list[str]]:
        """Converts a list of action packages into a list of tool definitions.

        Returns:
            A tuple containing a list of tool definitions and a list of
            configuration issues.
        """
        pass

    @abstractmethod
    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServer],
    ) -> tuple[list[ToolDefinition], list[str]]:
        """Converts a list of MCP servers into a list of tool definitions.

        Returns:
            A tuple containing a list of tool definitions and a list of
            configuration issues.
        """
        pass
