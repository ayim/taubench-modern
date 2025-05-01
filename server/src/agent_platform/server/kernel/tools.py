from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from agent_platform.core.actions import ActionPackage
from agent_platform.core.kernel import ToolsInterface
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.mcp import MCPServer
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition, ToolExecutionResult
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

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
        started_at = datetime.now(UTC)
        try:
            args_from_json = loads(tool_use.tool_input_raw or "{}")
        except Exception as e:
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw or "{}",
                output_raw=None,
                error=str(e),
                execution_started_at=started_at,
                execution_ended_at=datetime.now(UTC),
                execution_metadata={},
            )

        try:
            result = await tool_def.function(**args_from_json)
            # TODO: handling of various result types...
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw or "{}",
                output_raw=result,
                error=None,
                execution_started_at=started_at,
                execution_ended_at=datetime.now(UTC),
                execution_metadata={},
            )
        except Exception as e:
            return ToolExecutionResult(
                definition=tool_def,
                tool_call_id=tool_use.tool_call_id,
                execution_id=execution_id,
                input_raw=tool_use.tool_input_raw or "{}",
                output_raw=None,
                error=str(e),
                execution_started_at=started_at,
                execution_ended_at=datetime.now(UTC),
                execution_metadata={},
            )

    async def execute_pending_tool_calls(
        self,
        pending_tool_calls: list[PendingToolCall],
        message_to_update: ThreadMessageWithThreadState | None = None,
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
        while pending_tool_calls:
            # Pop as the caller should expect the list to end
            # up cleared after all tool calls have been executed
            tool_def, tool_use = pending_tool_calls.pop()
            # Update the tool to running in the thread state (if provided)
            if message_to_update:
                message_to_update.update_tool_running(tool_use.tool_call_id)
                await message_to_update.stream_delta()
            # Execute the tool in a separate task
            execution_tasks.append(
                create_task(self._safe_execute_tool(tool_def, tool_use)),
            )

        # Yield results as they complete
        for completed_task in as_completed(execution_tasks):
            result = await completed_task
            yield result
            # Update the tool to completed in the thread state (if provided)
            if message_to_update:
                message_to_update.update_tool_result(result)
                await message_to_update.stream_delta()

    def _deduplicate_tool_names(
        self,
        tools: list[ToolDefinition],
    ) -> tuple[list[ToolDefinition], list[str]]:
        """Checks for duplicate tool names and renames them with a unique postfix.

        Args:
            tools: The list of tool definitions to check.

        Returns:
            A tuple containing:
                - The list of tool definitions, potentially with renamed duplicates.
                - A list of strings describing any renaming issues found.
        """
        issues = []
        tool_names = [tool.name for tool in tools]
        processed_tools = list(tools)  # Create a copy to modify

        for idx, tool_name in enumerate(tool_names):
            if tool_names.count(tool_name) <= 1:
                continue

            # Duplicate tool name!
            unique_postfix = f"t{idx}"
            new_name = f"{tool_name}_{unique_postfix}"
            # Add an issue for the duplicate tool name
            issues.append(
                f"Tool with name {tool_name} is not unique across sources; "
                f"it has been renamed to {new_name}."
            )
            # Rename the tool in the list
            original_tool = processed_tools[idx]
            processed_tools[idx] = ToolDefinition(
                name=new_name,
                description=original_tool.description,
                input_schema=original_tool.input_schema,
                function=original_tool.function,
            )
            # Update the tool_names list as well to correctly detect
            # further duplicates
            tool_names[idx] = new_name

        return processed_tools, issues

    async def from_action_packages(
        self,
        action_packages: list[ActionPackage],
    ) -> tuple[list[ToolDefinition], list[str]]:
        from asyncio import create_task, gather

        tools = []
        issues = []

        async def safe_get_tool_definitions(action_package):
            try:
                return await action_package.to_tool_definitions(), None
            except Exception as e:
                detailed_issue = "Error aquiring tool definitions from action package:"
                detailed_issue += f"\nAction package: {action_package.name}"
                detailed_issue += f"\nAction package version: {action_package.version}"
                detailed_issue += f"\nAction package url: {action_package.url}"
                detailed_issue += f"\nException: {e!s}"
                return [], detailed_issue

        build_tasks = []
        seen_server_urls = set()
        for action_package in action_packages:
            # For our action servers, they can host MULTIPLE action
            # packages; then, when you ask the server for tools, it
            # will return all the tools from all the action packages.
            # So we need to _not_ request from the same server URL
            # more than once.
            if action_package.url in seen_server_urls:
                continue
            seen_server_urls.add(action_package.url)

            # Unique server URL, so add it to the list of tasks
            build_tasks.append(
                create_task(safe_get_tool_definitions(action_package)),
            )

        results = await gather(*build_tasks)
        for tools_list, issue in results:
            if issue:
                issues.append(issue)
            tools.extend(tools_list)

        # Deduplicate tool names across all collected action package tools
        tools, dedup_issues = self._deduplicate_tool_names(tools)
        issues.extend(dedup_issues)

        return tools, issues

    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServer],
    ) -> tuple[list[ToolDefinition], list[str]]:
        from asyncio import create_task, gather

        tools = []
        issues = []

        async def safe_get_tool_definitions(mcp_server):
            try:
                return await mcp_server.to_tool_definitions(), None
            except Exception as e:
                detailed_issue = "Error aquiring tool definitions from MCP server:"
                detailed_issue += f"\nMCP server: {mcp_server.name}"
                detailed_issue += f"\nMCP server url: {mcp_server.url}"
                detailed_issue += f"\nException: {e!s}"
                return [], detailed_issue

        build_tasks = []
        for mcp_server in mcp_servers:
            build_tasks.append(
                create_task(safe_get_tool_definitions(mcp_server)),
            )

        results = await gather(*build_tasks)
        for tools_list, issue in results:
            if issue:
                issues.append(issue)
            tools.extend(tools_list)

        # Deduplicate tool names across all collected MCP server tools
        tools, dedup_issues = self._deduplicate_tool_names(tools)
        issues.extend(dedup_issues)

        return tools, issues
