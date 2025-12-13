import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal

import pytest

from agent_platform.core.evals.agent_client import Tool, UnexpectedToolError
from agent_platform.core.evals.agent_client import ToolExecutionResult as ClientToolExecutionResult
from agent_platform.core.evals.live_executor import LiveToolExecutor
from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.tools.tool_execution_result import (
    ToolExecutionResult as KernelToolExecutionResult,
)


def _agent_message(
    *,
    tool_name: str,
    output: dict,
    sub_type: Literal["action-external"] = "action-external",
    metadata_tools: list[dict] | None = None,
) -> ThreadMessage:
    content = ThreadToolUsageContent(
        name=tool_name,
        tool_call_id=f"call-{tool_name}",
        arguments_raw=json.dumps({"arg": tool_name}),
        sub_type=sub_type,
        status="finished",
        result=json.dumps(output),
    )

    agent_metadata = {
        "model": "gpt-test",
        "platform": "test-platform",
        "tools": metadata_tools or [],
    }

    return ThreadMessage(content=[content], role="agent", agent_metadata=agent_metadata)


def test_from_conversation_filters_unused_tools() -> None:
    tool_definition = {
        "category": "action-tool",
        "name": "useful-tool",
        "description": "Does things",
        "input_schema": {"type": "object"},
    }
    unused_tool_definition = {
        "category": "action-tool",
        "name": "unused-tool",
        "description": "Not used",
        "input_schema": {"type": "object"},
    }

    message = _agent_message(
        tool_name="useful-tool",
        output={"status": "ok"},
        metadata_tools=[tool_definition, unused_tool_definition],
    )

    executor = ReplayToolExecutor.from_conversation([message])

    assert [tool.name for tool in executor.tools] == ["useful-tool"]
    assert executor.models == ["gpt-test"]
    assert executor.platforms == ["test-platform"]


def test_from_conversation_requires_tool_definition() -> None:
    message = _agent_message(tool_name="missing-tool", output={"status": "ok"})

    with pytest.raises(ValueError, match="Missing tool definitions"):
        ReplayToolExecutor.from_conversation([message])


def _tool_schema() -> dict:
    return {
        "type": "object",
        "properties": {"arg": {"type": "string"}},
        "required": ["arg"],
    }


class _FakeToolsInterface:
    def __init__(self, live_tool: ToolDefinition, calls: list[str]):
        self._live_tool = live_tool
        self._calls = calls

    async def execute_pending_tool_calls(self, pending_tool_calls, message_to_update=None, extra_headers=None):
        for _, tool_use in pending_tool_calls:
            payload = json.loads(tool_use.tool_input_raw)
            result_payload = await self._live_tool.function(**payload)
            self._calls.append(payload["arg"])
            yield KernelToolExecutionResult(
                definition=self._live_tool,
                tool_call_id=tool_use.tool_call_id,
                execution_id="exec-1",
                input_raw=tool_use.tool_input_raw,
                output_raw=result_payload,
                error=None,
                execution_started_at=datetime.now(UTC),
                execution_ended_at=datetime.now(UTC),
                execution_metadata={},
            )


@pytest.mark.asyncio
async def test_live_tool_executor_runs_live_tool() -> None:
    async def _live_tool(arg: str) -> dict:
        return {"status": arg}

    live_tool = ToolDefinition(
        name="demo-tool",
        description="demo",
        input_schema=_tool_schema(),
        category="action-tool",
        function=_live_tool,
    )

    executor = LiveToolExecutor([live_tool])

    calls: list[str] = []
    fake_kernel = SimpleNamespace(tools=_FakeToolsInterface(live_tool, calls))
    executor.attach_kernel(fake_kernel)  # type: ignore[arg-type]

    tool = Tool(
        tool_call_id="call-1",
        tool_name="demo-tool",
        input_raw=json.dumps({"arg": "value"}),
    )

    result = await executor.execute(tool)

    assert isinstance(result, ClientToolExecutionResult)
    assert json.loads(result.output) == {"status": "value"}
    assert calls == ["value"]


@pytest.mark.asyncio
async def test_live_tool_executor_requires_kernel() -> None:
    async def _live_tool(arg: str) -> dict:
        return {"status": arg}

    live_tool = ToolDefinition(
        name="demo-tool",
        description="demo",
        input_schema=_tool_schema(),
        category="action-tool",
        function=_live_tool,
    )

    executor = LiveToolExecutor([live_tool])

    tool = Tool(
        tool_call_id="call-1",
        tool_name="demo-tool",
        input_raw=json.dumps({"arg": "value"}),
    )

    with pytest.raises(UnexpectedToolError, match="kernel not attached"):
        await executor.execute(tool)


@pytest.mark.asyncio
async def test_live_tool_executor_missing_definition_errors() -> None:
    async def _live_tool(arg: str) -> dict:
        return {"status": arg}

    live_tool = ToolDefinition(
        name="demo-tool",
        description="demo",
        input_schema=_tool_schema(),
        category="action-tool",
        function=_live_tool,
    )

    executor = LiveToolExecutor([])
    fake_kernel = SimpleNamespace(tools=_FakeToolsInterface(live_tool, []))
    executor.attach_kernel(fake_kernel)  # type: ignore[arg-type]

    tool = Tool(
        tool_call_id="call-1",
        tool_name="demo-tool",
        input_raw=json.dumps({"arg": "value"}),
    )

    with pytest.raises(UnexpectedToolError, match="Cannot find live tool definition"):
        await executor.execute(tool)


@pytest.mark.asyncio
async def test_live_tool_executor_reports_gather_issues_on_missing_definition() -> None:
    executor = LiveToolExecutor([], issues=["Error acquiring tool definitions from action server"])
    executor.attach_kernel(SimpleNamespace(tools=None))  # type: ignore[arg-type]

    tool = Tool(
        tool_call_id="call-1",
        tool_name="demo-tool",
        input_raw=json.dumps({"arg": "value"}),
    )

    with pytest.raises(UnexpectedToolError) as exc:
        await executor.execute(tool)

    assert exc.value.details["tool"] == "demo-tool"
    assert exc.value.details["tool_gathering_issues"] == ["Error acquiring tool definitions from action server"]
