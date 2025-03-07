from agent_server_types_v2.kernel import ToolsInterface
from agent_server_types_v2.responses import ResponseMessage
from agent_server_types_v2.tools import ToolDefinition, ToolExecutionResult
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerToolsInterface(ToolsInterface, UsesKernelMixin):
    """Manages building and execution of agent actions,
    internal tools, and CA-defined tools."""

    async def execute_tools_from_model_response(
        self, tools: list[ToolDefinition], response: ResponseMessage,
    ) -> list[ToolExecutionResult]:
        """Executes tools from a model response.

        Arguments:
            tools: A list of tool definitions to execute.
            response: The model response containing tool calls.

        Returns:
            A list of tool execution results.
        """
        raise NotImplementedError("Not implemented")
