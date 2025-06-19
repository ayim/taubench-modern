import asyncio
import json
from collections import Counter
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import structlog

from agent_platform.core.actions import ActionPackage
from agent_platform.core.kernel import ToolsInterface
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.mcp import MCPServer
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.streaming.delta import StreamingDeltaRequestToolExecution
from agent_platform.core.streaming.incoming import IncomingDeltaClientToolResult
from agent_platform.core.tools import ToolDefinition, ToolExecutionResult
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin
from agent_platform.server.kernel.tools_caching import (
    ToolDefinitionCache,
)

PendingToolCall = tuple[ToolDefinition, ResponseToolUseContent]


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AgentServerToolsInterface(ToolsInterface, UsesKernelMixin):
    """Manages building and execution of agent actions,
    internal tools, and CA-defined tools."""

    _cache: ToolDefinitionCache = ToolDefinitionCache()

    # ------------------------------------------------------ tool execution methods

    async def _safe_execute_tool(
        self,
        tool_def: ToolDefinition,
        tool_use: ResponseToolUseContent,
        extra_headers: dict | None = None,
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
        result_output = None
        error_message = None
        try:
            args_from_json = loads(tool_use.tool_input_raw or "{}")
        except Exception as e:
            error_message = str(e)
        else:
            try:
                result = await tool_def.function(
                    **args_from_json,
                    extra_headers=extra_headers,
                )

                # TODO: handling of various result types...
                if isinstance(result, dict):
                    # Check for error_code format
                    if "error_code" in result and result["error_code"] != "":
                        error_code = result["error_code"]
                        error_message = result.get("message", "Unknown error")
                        error_message = f"{error_code}: {error_message}"
                        result_output = result
                    # Check for {"result": None, "error": "error-message"} format
                    elif (
                        "result" in result
                        and result["result"] is None
                        and "error" in result
                        and result["error"]
                    ):
                        error_message = result["error"]
                        result_output = result
                    else:
                        result_output = result

                # Handles all primitive types that action servers can return
                elif result is None or isinstance(result, str | int | float | bool):
                    result_output = result  # This will be stringified later in the run
                else:
                    # We received a malformed result from the tool
                    error_message = "Received a malformed result from the tool"
                    result_output = result
            except Exception as e:
                error_message = str(e)

        return ToolExecutionResult(
            **tool_result_args,
            output_raw=result_output,
            error=error_message,
            execution_ended_at=datetime.now(UTC),
        )

    async def _safe_execute_client_tool(
        self,
        tool_def: ToolDefinition,
        tool_use: ResponseToolUseContent,
    ) -> ToolExecutionResult:
        """Request tool execution from the client and optionally await the result."""
        execution_id = str(uuid4())
        started_at = datetime.now(UTC)

        await self.kernel.outgoing_events.dispatch(
            StreamingDeltaRequestToolExecution(
                tool_name=tool_def.name,
                tool_call_id=tool_use.tool_call_id,
                input_raw=tool_use.tool_input_raw or "{}",
                timestamp=started_at,
                # Only client-exec-tool requires execution (client-info-tool doesn't)
                requires_execution=tool_def.category == "client-exec-tool",
            ),
        )
        if tool_def.category == "client-exec-tool":
            try:
                # Use the new wait_for_event method with a predicate
                reply = await self.kernel.incoming_events.wait_for_event(
                    lambda event: (
                        isinstance(event, IncomingDeltaClientToolResult)
                        and event.tool_call_id == tool_use.tool_call_id
                    )
                )
                # Cast to the specific type since we know from the predicate it's
                # IncomingDeltaClientToolResult
                reply = cast(IncomingDeltaClientToolResult, reply)
                output_raw = reply.result.get("output")
                error = reply.result.get("error")
            except asyncio.CancelledError:
                # Handle graceful cancellation (e.g., websocket disconnect)
                output_raw = None
                error = "Tool execution cancelled due to client disconnection"
        else:
            output_raw = {}
            error = None

        return ToolExecutionResult(
            definition=tool_def,
            tool_call_id=tool_use.tool_call_id,
            execution_id=execution_id,
            input_raw=tool_use.tool_input_raw or "{}",
            output_raw=output_raw,
            error=error,
            execution_started_at=started_at,
            execution_ended_at=datetime.now(UTC),
            execution_metadata={},
        )

    @classmethod
    def _create_tool_call_inputs(cls, pending_tool_calls):
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

    @classmethod
    def _deduplicate_tool_names(
        cls,
        tools: list[ToolDefinition],
    ) -> tuple[list[ToolDefinition], list[str]]:
        """
        Checks for duplicate tool names. The first occurrence of each name
        remains unchanged, while any subsequent occurrences of that same name
        are renamed with a numeric suffix (e.g., "MyTool", "MyTool_2", "MyTool_3", ...).

        Returns:
            A tuple of:
                - The updated list of ToolDefinitions (potentially renamed).
                - A list of messages explaining any renaming that occurred.
        """
        # Count how many times each name appears
        name_counter = Counter(tool.name for tool in tools)
        # We'll track how many times we've assigned a new name
        rename_count = Counter()

        updated_tools: list[ToolDefinition] = []
        issues: list[str] = []

        for tool in tools:
            # If no duplicates for this name, just append as-is
            if name_counter[tool.name] <= 1:
                updated_tools.append(tool)
                continue

            # There's a duplicate for this name. We always allow the first occurrence
            # to keep its name, and rename subsequent occurrences.
            rename_count[tool.name] += 1
            occurrence_index = rename_count[tool.name]

            if occurrence_index == 1:
                # This is the first time we see it in the loop,
                # so keep its original name
                updated_tools.append(tool)
            else:
                # Rename the second or subsequent time, e.g.
                # "toolname_2", "toolname_3", ...
                new_name = f"{tool.name}_{occurrence_index}"
                issues.append(
                    f"Tool with name '{tool.name}' is duplicated. Renaming occurrence "
                    f"#{occurrence_index} to '{new_name}'."
                )
                updated_tools.append(
                    ToolDefinition(
                        name=new_name,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        function=tool.function,
                    )
                )

        return updated_tools, issues

    async def execute_pending_tool_calls(
        self,
        pending_tool_calls: list[PendingToolCall],
        message_to_update: ThreadMessageWithThreadState | None = None,
        extra_headers: dict | None = None,
    ) -> AsyncGenerator[ToolExecutionResult, None]:
        """Executes pending tool calls.

        By default, this method will pass extra header with the
        agent, user, and thread ID to the tool server.

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
            attributes=self.kernel.get_standard_span_attributes(
                extra_attributes={
                    "langsmith.span.kind": "chain",
                    "langsmith.trace.name": "execute_pending_tool_calls",
                    "tool_count": len(pending_calls_copy) if pending_calls_copy else 0,
                },
            ),
        ) as span:
            # Format tool call inputs for telemetry
            if pending_calls_copy:
                tool_calls_input = self._create_tool_call_inputs(pending_calls_copy)
                span.set_attribute("input.value", json.dumps(tool_calls_input))
                span.add_event(f"Starting execution of {len(pending_calls_copy)} tools")

            base_headers = (extra_headers or {}) | {
                "x-invoked_by_assistant_id": self.kernel.agent.agent_id,
                "x-invoked_on_behalf_of_user_id": self.kernel.user.cr_user_id,
                "x-invoked_for_thread_id": self.kernel.thread.thread_id,
            }

            # Create tasks for each tool call
            execution_tasks = []
            while pending_tool_calls:
                # Pop as the caller should expect the list to end up cleared
                tool_def, tool_use = pending_tool_calls.pop()
                run_headers = dict(base_headers)
                run_headers["x-action_invocation_id"] = tool_use.tool_call_id

                # Update the tool to running in the thread state (if provided)
                if message_to_update:
                    message_to_update.update_tool_running(tool_use.tool_call_id)
                    await message_to_update.stream_delta()

                # Execute the tool in a separate task
                if tool_def.category in {"client-exec-tool", "client-info-tool"}:
                    # These are client-provided tools for which we either block
                    # and wait for a result over the event bus, or just simply
                    # signal the client with the tool input and immediately execute
                    # with empty output.
                    execution_tasks.append(
                        create_task(
                            self._safe_execute_client_tool(tool_def, tool_use),
                        ),
                    )
                else:
                    # These are the classic "action-tool" and "mcp-tool" types.
                    execution_tasks.append(
                        create_task(
                            self._safe_execute_tool(
                                tool_def,
                                tool_use,
                                extra_headers=run_headers,
                            ),
                        ),
                    )

            # Yield results as they complete
            for completed_task in as_completed(execution_tasks):
                try:
                    result = await completed_task
                except asyncio.CancelledError:
                    # Task was cancelled (e.g., due to websocket disconnect)
                    # We can't yield a result for this task, so just continue
                    # The cancellation will be handled by the individual tool execution methods
                    continue

                # Create a span for this specific tool execution
                with self.kernel.ctx.start_span(
                    f"tool_execution_{result.definition.name}",
                    attributes=self.kernel.get_standard_span_attributes(
                        extra_attributes={
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
                        },
                    ),
                ) as tool_span:
                    # Record success or failure
                    tool_span.set_attribute("tool.success", result.error is None)

                    # Format the result for tracing
                    formatted_result = AgentServerToolsInterface._format_tool_result_for_trace(
                        result
                    )
                    tool_span.set_attribute("output.value", json.dumps(formatted_result))

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

    # -------------------------------------------------------- cache operations

    async def _fetch_action_tools(
        self,
        action_packages: list[ActionPackage],
        additional_headers: dict | None = None,
    ) -> tuple[list[ToolDefinition], list[str]]:
        """Downloads & returns tool defs."""
        tools: list[ToolDefinition] = []
        issues: list[str] = []

        async def safe(ap: ActionPackage):
            try:
                logger.info(f"Fetching tool definitions from action package: {ap.url}")
                return await ap.to_tool_definitions(additional_headers), None
            except Exception as exc:
                detailed = (
                    "Error acquiring tool definitions from action package:"
                    f"\n  name={ap.name!r} version={ap.version!r} url={ap.url!r}"
                    f"\n  exception={exc!s}"
                )
                logger.warning(
                    f"Error fetching tool definitions from action package: {detailed}",
                )
                return [], detailed

        tasks = []
        for pkg in action_packages:
            if not pkg.url:
                continue
            tasks.append(asyncio.create_task(safe(pkg)))

        for tdefs, issue in await asyncio.gather(*tasks):
            tools.extend(tdefs)
            if issue:
                issues.append(issue)

        return tools, issues

    async def _fetch_mcp_tools(
        self,
        mcp_servers: list[MCPServer],
        additional_headers: dict | None = None,
    ) -> tuple[list[ToolDefinition], list[str]]:
        """Same contract as _fetch_action_tools()."""
        tools: list[ToolDefinition] = []
        issues: list[str] = []

        async def safe(srv: MCPServer):
            try:
                logger.info(f"Fetching tool definitions from MCP server: {srv.url}")
                return await srv.to_tool_definitions(additional_headers), None
            except Exception as exc:
                detailed = (
                    "Error acquiring tool definitions from MCP server:"
                    f"\n  name={srv.name!r} url={srv.url!r}"
                    f"\n  exception={exc!s}"
                )
                logger.warning(
                    f"Error fetching tool definitions from MCP server: {detailed}",
                )
                return [], detailed

        tasks = [asyncio.create_task(safe(srv)) for srv in mcp_servers]
        for tdefs, issue in await asyncio.gather(*tasks):
            tools.extend(tdefs)
            if issue:
                issues.append(issue)

        return tools, issues

    # --------------------------------------------- public cache-aware methods

    async def from_action_packages(
        self,
        action_packages: list[ActionPackage],
        # Headers to be added to the request at
        # tool definition time (can be overriden at
        # tool invocation time using extra_headers)
        additional_headers: dict | None = None,
    ) -> tuple[list[ToolDefinition], list[str]]:
        all_tools: list[ToolDefinition] = []
        all_issues: list[str] = []

        # Group packages by URL so we only fetch from each server once but still
        # respect differing allowed_actions across packages that share a URL.
        packages_by_url: dict[str, list[ActionPackage]] = {}
        for pkg in action_packages:
            if not pkg.url:
                continue
            packages_by_url.setdefault(pkg.url, []).append(pkg)

        async def _fetch(ap: ActionPackage, additional_headers: dict | None = None):
            return await self._fetch_action_tools([ap], additional_headers=additional_headers)

        for url, pkgs in packages_by_url.items():
            # Always fetch the **full** tool set once per URL and cache it.  We
            # then filter locally based on the union of allowed actions across
            # all packages referencing that URL.  This avoids dropping tools if
            # a later call has more permissive allowed_actions than whatever was
            # first cached for the same URL.

            # Template package is just for URL/API key; allowed_actions=[] means
            # "fetch everything".
            template = pkgs[0].copy()
            template = ActionPackage(
                name=template.name,
                organization=template.organization,
                version=template.version,
                url=template.url,
                api_key=template.api_key,
                allowed_actions=[],
            )

            subtools, subissues = await self._cache.get_or_fetch(
                kind="action_packages",
                key=url,
                fetch_coro=_fetch(template, additional_headers=additional_headers),
            )

            # Compute the merged list of allowed actions for *this call*.
            allow_all = any(len(p.allowed_actions) == 0 for p in pkgs)
            if not allow_all:
                allowed = {action for p in pkgs for action in p.allowed_actions}
                subtools = [td for td in subtools if td.name in allowed]

            all_tools.extend(subtools)
            all_issues.extend(subissues)

        # Now deduplicate any conflicting tool names across all packages
        all_tools, dups = self._deduplicate_tool_names(all_tools)
        all_issues.extend(dups)
        return all_tools, all_issues

    async def from_mcp_servers(
        self,
        mcp_servers: list[MCPServer],
        # Headers to be added to the request at
        # tool definition time (can be overriden at
        # tool invocation time using extra_headers)
        # NOTE: MCP doesn't really seem to support this at the moment...
        additional_headers: dict | None = None,
    ) -> tuple[list[ToolDefinition], list[str]]:
        all_tools = []
        all_issues = []
        seen_urls = set()

        async def _fetch(srv: MCPServer, additional_headers: dict | None = None):
            return await self._fetch_mcp_tools(
                [srv],
                additional_headers=additional_headers,
            )

        for srv in mcp_servers:
            if srv.url and srv.url in seen_urls:
                continue  # skip any duplicate URLs (this shouldn't really
                # happen, but just in case...)

            if srv.url:
                seen_urls.add(srv.url)

            subtools, subissues = await self._cache.get_or_fetch(
                kind="mcp_servers",
                key=srv.cache_key,
                fetch_coro=_fetch(srv, additional_headers=additional_headers),
            )
            all_tools.extend(subtools)
            all_issues.extend(subissues)

        # Deduplicate
        all_tools, dups = self._deduplicate_tool_names(all_tools)
        all_issues.extend(dups)
        return all_tools, all_issues
