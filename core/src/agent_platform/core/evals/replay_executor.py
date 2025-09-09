import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import structlog

from agent_platform.core.evals.agent_client import Tool, ToolExecutionResult, ToolExecutor
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = structlog.get_logger(__name__)


@dataclass
class ExpectedCall:
    tool_name: str
    expected_args: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None


class ReplayToolExecutor(ToolExecutor):
    """
    Replays tool calls from a captured conversation.
    Enforces both call order and argument equality (deep compare).
    """

    def __init__(
        self,
        expected_calls: list[ExpectedCall],
        *,
        models: list[str],
        platforms: list[str],
        tools: list[ToolDefinition],
        strict_args: bool = True,
    ):
        self._calls = expected_calls
        self._i = 0
        self._strict = strict_args
        self.models = models
        self.platforms = platforms
        self.tools = tools

    @classmethod
    def from_conversation(cls, messages: list[ThreadMessage]) -> "ReplayToolExecutor":  # noqa: C901
        expected: list[ExpectedCall] = []
        models = set()
        platforms = set()
        tools_by_name: dict[str, ToolDefinition] = {}

        for msg in messages:
            for item in msg.content:
                if isinstance(item, ThreadToolUsageContent):
                    tool_name = item.name
                    # Inputs/outputs are JSON strings in the provided log.
                    tool_args = item.arguments_raw
                    tool_result = item.result

                    try:
                        expected_args = json.loads(tool_args)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Bad input JSON for {tool_name}: {e}\n{tool_args}") from e

                    try:
                        output = json.loads(tool_result) if tool_result is not None else None
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Bad output JSON for {tool_name}: {e}\n{tool_result}"
                        ) from e

                    expected.append(ExpectedCall(tool_name, expected_args, output, item.error))

            metadata = msg.agent_metadata

            model = metadata.get("model")
            if model is not None:
                models.add(model)

            platform = metadata.get("platform")
            if platform is not None:
                platforms.add(platform)

            for tool in metadata.get("tools", []):
                if isinstance(tool, str):
                    raise ValueError("Tool should be an object")

                tool_name = tool.get("name")
                if not tool_name:
                    raise ValueError("Tool should have a name")

                tool_desc = tool.get("description", "")
                input_schema = tool.get("input_schema", {})

                if tool_name not in tools_by_name:
                    tools_by_name[tool_name] = ToolDefinition(
                        name=tool_name,
                        description=tool_desc,
                        input_schema=deepcopy(input_schema),
                        category="client-exec-tool",
                    )
                else:
                    # no op: there should not be duplicate names
                    logger.info(f"Found duplicate name for tool {tool_name}")

        return cls(
            expected,
            models=sorted(models),
            platforms=sorted(platforms),
            tools=sorted(tools_by_name.values(), key=lambda tool: tool.name),
        )

    def _assert_next(self, tool: Tool) -> ExpectedCall:
        logger.info(f"Intercepted tool {tool.tool_name}")
        if self._i >= len(self._calls):
            raise AssertionError(
                f"Unexpected tool call #{self._i + 1}: {tool.tool_name}. "
                "No more calls were recorded."
            )

        exp = self._calls[self._i]

        if tool.tool_name != exp.tool_name:
            raise AssertionError(
                f"Tool name mismatch at call #{self._i + 1}.\n"
                f"  expected: {exp.tool_name}\n"
                f"  got     : {tool.tool_name}"
            )

        try:
            actual_args = json.loads(tool.input_raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Bad actual input JSON for {tool.tool_name}: {e}\n{tool.input_raw}"
            ) from e

        # Args check (deep equality). If needed, you can customize to allow
        # reordering or extra keys using self._strict.
        if self._strict:
            if actual_args != exp.expected_args:
                raise AssertionError(
                    f"Arguments mismatch at call #{self._i + 1} for '{tool.tool_name}'.\n"
                    f"  expected args: {json.dumps(exp.expected_args, indent=2, sort_keys=True)}\n"
                    f"  got args     : {json.dumps(actual_args, indent=2, sort_keys=True)}"
                )
        else:
            # Non-strict: ensure all expected keys match and values are equal.
            for k, v in exp.expected_args.items():
                if k not in tool.input_raw or actual_args[k] != v:
                    raise AssertionError(
                        f"Non-strict arg mismatch at call #{self._i + 1} for '{tool.tool_name}'. "
                        f"Key '{k}' expected value {v}, got {actual_args.get(k, '<missing>')}"
                    )

        logger.info(f"Tool {tool.tool_name} mocked with stored results")
        return exp

    async def execute(self, tool: Tool) -> ToolExecutionResult:
        exp = self._assert_next(tool)
        self._i += 1
        return ToolExecutionResult(error=exp.error, output=json.dumps(exp.output))

    def assert_all_consumed(self) -> None:
        """Optional: call at the end of a test to ensure no missing calls."""
        if self._i != len(self._calls):
            remaining = len(self._calls) - self._i
            raise AssertionError(f"{remaining} recorded tool call(s) were not executed.")
