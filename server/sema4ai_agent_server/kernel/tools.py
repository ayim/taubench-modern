from collections.abc import AsyncGenerator
from datetime import datetime

from agent_server_types_v2.actions import ActionPackage
from agent_server_types_v2.kernel import ToolsInterface
from agent_server_types_v2.mcp import MCPServer
from agent_server_types_v2.responses.content.tool_use import ResponseToolUseContent
from agent_server_types_v2.tools import ToolDefinition, ToolExecutionResult
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin

PendingToolCall = tuple[ToolDefinition, ResponseToolUseContent]

class AgentServerToolsInterface(ToolsInterface, UsesKernelMixin):
    """Manages building and execution of agent actions,
    internal tools, and CA-defined tools."""

    async def _safe_execute_tool(
        self,
        tool_def: ToolDefinition,
        tool_use: ResponseToolUseContent,
    ) -> ToolExecutionResult:
        from json import loads
        from uuid import uuid4

        execution_id = str(uuid4())
        started_at = datetime.now()
        try:
            args_from_json = loads(tool_use.tool_input_raw or "{}")
        except Exception as e:
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw,
                output_raw=None,
                error=str(e),
                execution_started_at=started_at,
                execution_ended_at=datetime.now(),
                execution_metadata={},
            )

        try:
            result = await tool_def.function(**args_from_json)
            # TODO: handling of various result types...
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw,
                output_raw=result,
                error=None,
                execution_started_at=started_at,
                execution_ended_at=datetime.now(),
                execution_metadata={},
            )
        except Exception as e:
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw,
                output_raw=None,
                error=str(e),
                execution_started_at=started_at,
                execution_ended_at=datetime.now(),
                execution_metadata={},
            )

    async def execute_pending_tool_calls(
        self,
        pending_tool_calls: list[PendingToolCall],
    ) -> AsyncGenerator[ToolExecutionResult, None]:
        """Executes pending tool calls.

        Arguments:
            pending_tool_calls: A list of pending tool calls to execute.

        Yields:
            Tool execution results as they complete.
        """
        from asyncio import as_completed, create_task

        # Create tasks for each tool call
        execution_tasks = []
        for tool_def, tool_use in pending_tool_calls:
            # Execute the tool in a separate task
            execution_tasks.append(
                create_task(self._safe_execute_tool(tool_def, tool_use)),
            )

        # Yield results as they complete
        for completed_task in as_completed(execution_tasks):
            result = await completed_task
            yield result

    async def from_action_packages(
        self,
        action_packages: list[ActionPackage],
    ) -> list[ToolDefinition]:
        from asyncio import create_task, gather

        build_tasks = []
        for action_package in action_packages:
            build_tasks.append(
                create_task(action_package.to_tool_definitions()),
            )

        results = await gather(*build_tasks)
        return [
            tool
            for result in results
            for tool in result
        ]

    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServer],
    ) -> list[ToolDefinition]:
        from asyncio import create_task, gather

        build_tasks = []
        for mcp_server in mcp_servers:
            build_tasks.append(
                create_task(mcp_server.to_tool_definitions()),
            )

        results = await gather(*build_tasks)
        return [
            tool
            for result in results
            for tool in result
        ]
