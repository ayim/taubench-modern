import json
from typing import Literal

import pytest

from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent


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
