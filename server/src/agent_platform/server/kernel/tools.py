import json
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

import structlog

from agent_platform.core.actions import ActionPackage
from agent_platform.core.agent.agent import Agent
from agent_platform.core.kernel import ToolsInterface
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.mcp import MCPServer
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition, ToolExecutionResult
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

PendingToolCall = tuple[ToolDefinition, ResponseToolUseContent]


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AgentServerToolsInterface(ToolsInterface, UsesKernelMixin):
    """Manages building and execution of agent actions,
    internal tools, and CA-defined tools."""

    # Class-level caches
    _action_packages_cache: ClassVar[
        dict[
            frozenset[str],
            tuple[list[ToolDefinition], list[str]],
        ]
    ] = {}
    _mcp_servers_cache: ClassVar[
        dict[
            frozenset[str],
            tuple[list[ToolDefinition], list[str]],
        ]
    ] = {}

    async def _safe_execute_tool(
        self,
        tool_def: ToolDefinition,
        tool_use: ResponseToolUseContent,
    ) -> ToolExecutionResult:
        from json import loads

        execution_id = str(uuid4())
        started_at = datetime.now(UTC)
        tool_result_args = {
            "definition": tool_def,
            "tool_call_id": tool_use.tool_call_id,
            "execution_id": execution_id,
            "input_raw": tool_use.tool_input_raw or "{}",
            "execution_started_at": started_at,
            "execution_metadata": {},
        }
        try:
            args_from_json = loads(tool_use.tool_input_raw or "{}")
        except Exception as e:
            return ToolExecutionResult(
                **tool_result_args,
                output_raw=None,
                error=str(e),
                execution_ended_at=datetime.now(UTC),
            )

        try:
            result = await tool_def.function(**args_from_json)
            # TODO: handling of various result types...
            return ToolExecutionResult(
                **tool_result_args,
                output_raw=result,
                error=None,
                execution_ended_at=datetime.now(UTC),
            )
        except Exception as e:
            return ToolExecutionResult(
                **tool_result_args,
                output_raw=None,
                error=str(e),
                execution_ended_at=datetime.now(UTC),
            )

    def _create_tool_call_inputs(self, pending_tool_calls):
        """Create the formatted tool call inputs for telemetry.

        Args:
            pending_tool_calls: List of pending tool calls

        Returns:
            Formatted tool calls input list
        """
        tool_calls_input = []
        for tool_def, tool_use in pending_tool_calls:
            try:
                args_dict = json.loads(tool_use.tool_input_raw or "{}")
            except Exception:
                args_dict = {}

            tool_calls_input.append(
                {
                    "name": tool_def.name,
                    "args": args_dict,
                    "id": tool_use.tool_call_id,
                    "type": "tool_call",
                }
            )

        return tool_calls_input

    @classmethod
    def _format_tool_result_for_trace(cls, result: ToolExecutionResult):
        """Format a tool execution result for tracing.

        Args:
            result: The tool execution result

        Returns:
            Formatted dictionary for tracing
        """
        return {
            "content": str(result.output_raw) if result.error is None else result.error,
            "additional_kwargs": {"name": result.definition.name},
            "response_metadata": {},
            "type": "tool",
            "id": result.execution_id,
            "tool_call_id": result.tool_call_id,
            "status": "success" if result.error is None else "error",
        }

    async def execute_pending_tool_calls(
        self,
        pending_tool_calls: list[PendingToolCall],
        message_to_update: ThreadMessageWithThreadState | None = None,
    ) -> AsyncGenerator[ToolExecutionResult, None]:
        """Executes pending tool calls.

        Arguments:
            pending_tool_calls: A list of pending tool calls to execute.
            message_to_update: Optional message to update with tool execution progress.

        Yields:
            Tool execution results as they complete.
        """
        from asyncio import as_completed, create_task

        from opentelemetry.trace import StatusCode

        # Create a copy of the pending calls for telemetry
        pending_calls_copy = list(pending_tool_calls)

        # Set up the span for tracing the batch of tool calls
        with self.kernel.ctx.start_span(
            "execute_pending_tool_calls",
            attributes={
                "langsmith.span.kind": "chain",
                "langsmith.trace.name": "execute_pending_tool_calls",
                "tool_count": len(pending_calls_copy) if pending_calls_copy else 0,
                "agent.id": self.kernel.agent.agent_id,
                "thread.id": self.kernel.thread.thread_id,
            },
        ) as span:
            # Format tool call inputs for telemetry
            if pending_calls_copy:
                tool_calls_input = self._create_tool_call_inputs(pending_calls_copy)
                span.set_attribute("input.value", json.dumps(tool_calls_input))
                span.add_event(f"Starting execution of {len(pending_calls_copy)} tools")

            # Create tasks for each tool call
            execution_tasks = []
            while pending_tool_calls:
                # Pop as the caller should expect the list to end up cleared
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
            all_results = []
            for completed_task in as_completed(execution_tasks):
                result = await completed_task
                all_results.append(result)

                # Create a span for this specific tool execution
                with self.kernel.ctx.start_span(
                    f"tool_execution_{result.definition.name}",
                    attributes={
                        "langsmith.span.kind": "tool",
                        "langsmith.trace.name": f"Tool: {result.definition.name}",
                        "tool.name": result.definition.name,
                        "tool.call_id": result.tool_call_id,
                        "tool.execution_id": result.execution_id,
                        "tool.input": result.input_raw,
                        "input.value": json.dumps(
                            {
                                "name": result.definition.name,
                                "args": json.loads(result.input_raw)
                                if result.input_raw
                                else {},
                                "id": result.tool_call_id,
                                "type": "tool_call",
                            }
                        ),
                        "agent.id": self.kernel.agent.agent_id,
                        "thread.id": self.kernel.thread.thread_id,
                    },
                ) as tool_span:
                    # Record success or failure
                    tool_span.set_attribute("tool.success", result.error is None)

                    # Format the result for tracing
                    formatted_result = (
                        AgentServerToolsInterface._format_tool_result_for_trace(result)
                    )
                    tool_span.set_attribute(
                        "output.value", json.dumps(formatted_result)
                    )

                    # Set error info if applicable
                    if result.error:
                        tool_span.set_attribute("error", result.error)
                        tool_span.set_status(StatusCode.ERROR)

                # Log completion event in the parent span
                span.add_event(
                    f"Tool {result.definition.name} completed",
                    {
                        "success": result.error is None,
                        "tool_call_id": result.tool_call_id,
                    },
                )

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
            logger.info(f"Deduplicating tool name {tool_name} to {new_name}")
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
        self, action_packages: list[ActionPackage], additional_headers: dict | None
    ) -> tuple[list[ToolDefinition], list[str]]:
        # Generate a cache key from the unique URLs of the action packages
        cache_key: frozenset[str] = frozenset(
            ap.url for ap in action_packages if ap.url
        )
        if cache_key in self.__class__._action_packages_cache:
            logger.info(f"Cache hit for action packages with key: {cache_key}")
            return self.__class__._action_packages_cache[cache_key]

        start_time = time.time()
        logger.info(
            f"Cache miss for action packages with key: {cache_key}. Fetching tools."
        )

        from asyncio import create_task, gather

        tools = []
        issues = []

        async def safe_get_tool_definitions(action_package: ActionPackage):
            try:
                return await action_package.to_tool_definitions(
                    additional_headers=additional_headers
                ), None
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

        # Store the result in the class-level cache before returning
        self.__class__._action_packages_cache[cache_key] = (tools, issues)
        logger.info(f"Cached tools for action packages with key: {cache_key}")
        logger.info(f"Time taken to fetch tools: {time.time() - start_time} seconds")
        return tools, issues

    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServer],
    ) -> tuple[list[ToolDefinition], list[str]]:
        # Generate a cache key from the unique URLs of the MCP servers
        cache_key: frozenset[str] = frozenset(s.url for s in mcp_servers if s.url)
        if cache_key in self.__class__._mcp_servers_cache:
            logger.info(f"Cache hit for MCP servers with key: {cache_key}")
            return self.__class__._mcp_servers_cache[cache_key]

        start_time = time.time()
        logger.info(
            f"Cache miss for MCP servers with key: {cache_key}. Fetching tools."
        )

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

        # Store the result in the class-level cache before returning
        self.__class__._mcp_servers_cache[cache_key] = (tools, issues)
        logger.info(f"Cached tools for MCP servers with key: {cache_key}")
        logger.info(f"Time taken to fetch tools: {time.time() - start_time} seconds")
        return tools, issues

    @classmethod
    def clear_tool_cache(cls) -> None:
        """Clears the class-level cache for tool definitions
        from action packages and MCP servers."""
        logger.info(
            "Clearing all tool caches (_action_packages_cache and _mcp_servers_cache)."
        )
        cls._action_packages_cache.clear()
        cls._mcp_servers_cache.clear()

    @classmethod
    def clear_tools_for_agent(cls, agent: Agent) -> None:
        """Clears the cached tools associated with a specific agent.

        Args:
            agent: The agent to clear tool cache entries for.
        """
        actions_cache_key = frozenset(ap.url for ap in agent.action_packages if ap.url)
        mcp_servers_cache_key = frozenset(s.url for s in agent.mcp_servers if s.url)

        if actions_cache_key in cls._action_packages_cache:
            cls._action_packages_cache.pop(actions_cache_key, None)
            logger.info(
                f"Cleared action packages cache for agent {agent.agent_id} "
                f"with key: {actions_cache_key}"
            )
        else:
            logger.info(
                f"No action packages cache found for agent {agent.agent_id} "
                f"with key: {actions_cache_key}"
            )

        if mcp_servers_cache_key in cls._mcp_servers_cache:
            cls._mcp_servers_cache.pop(mcp_servers_cache_key, None)
            logger.info(
                f"Cleared MCP servers cache for agent {agent.agent_id} "
                f"with key: {mcp_servers_cache_key}"
            )
        else:
            logger.info(
                f"No MCP servers cache found for agent {agent.agent_id} "
                f"with key: {mcp_servers_cache_key}"
            )
