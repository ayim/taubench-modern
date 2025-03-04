from abc import ABC, abstractmethod

from agent_server_types_v2.responses import ResponseMessage
from agent_server_types_v2.tools import ToolDefinition, ToolExecutionResult


class ToolsInterface(ABC):
    """Manages building and execution of agent actions, internal tools, and CA-defined tools."""

    @abstractmethod
    async def execute_tools_from_model_response(
        self,
        tools: list[ToolDefinition],
        response: ResponseMessage,
    ) -> list[ToolExecutionResult]:
        """Executes tools from a model response.

        Arguments:
            tools: A list of tool definitions to execute.
            response: The model response containing tool calls.

        Returns:
            A list of tool execution results.
        """
        pass
