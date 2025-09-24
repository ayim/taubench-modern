import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import structlog

from agent_platform.core.evals.agent_client import (
    Tool,
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutor,
    UnexpectedToolError,
)
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


class ReplayDriftError(ToolExecutionError):
    """Represents a mismatch between the expected and actual tool call during replay."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, details)


class DriftType(str, Enum):
    ORDER_MISMATCH = "ORDER_MISMATCH"
    NAME_MISMATCH = "NAME_MISMATCH"
    ARG_MISMATCH = "ARG_MISMATCH"
    EXTRA_ACTUAL_CALL = "EXTRA_ACTUAL_CALL"
    MISSING_ACTUAL_CALL = "MISSING_ACTUAL_CALL"
    LEFTOVER_RECORDED_CALLS = "LEFTOVER_RECORDED_CALLS"


@dataclass
class DriftEvent:
    index_before: int
    drift_type: DriftType
    message: str
    expected_tool: str | None = None
    actual_tool: str | None = None
    expected_args: dict[str, Any] | None = None
    actual_args: dict[str, Any] | None = None
    repair_action: str | None = None

    @classmethod
    def model_validate(cls, data: dict) -> "DriftEvent":
        if data["drift_type"]:
            data["drift_type"] = DriftType(data["drift_type"])

        return cls(**data)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class DriftPolicy:
    # If True, we allow subset-equality in args (all expected pairs must match actual),
    # plus numeric tolerance and simple type coercions (e.g., "3" -> 3).
    allow_arg_subset: bool = True
    numeric_epsilon: float = 1e-9
    coerce_json_number_like: bool = True

    # Upper bound on how many drifts we will attempt to repair before failing.
    max_events: int = 10

    # If True, all expected calls should be consumed
    assert_all_consumed: bool = True

    # TODO If True, we try to find the matching recorded call ahead and consume it (reordering).
    # allow_reorder: bool = True


def _coerce_equal(a: Any, b: Any, eps: float, coerce_num: bool) -> bool:
    """Loose equality: allows small float diffs and number-like strings if enabled."""
    if a == b:
        return True
    if coerce_num:
        # Try number-like coercion
        for x, y in ((a, b), (b, a)):
            if isinstance(x, str):
                try:
                    xv = float(x) if "." in x or "e" in x.lower() else int(x)
                    if isinstance(y, int | float):
                        if isinstance(xv, float) or isinstance(y, float):
                            return abs(float(xv) - float(y)) <= eps
                        return xv == y
                except ValueError:
                    pass
    # Try numeric epsilon if both numeric
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) <= eps
    return False


@dataclass
class ArgMismatchDetail:
    path: str
    expected: Any
    actual: Any
    reason: str


def _subset_args_check(
    expected: dict[str, Any],
    actual: dict[str, Any],
    eps: float,
    coerce_num: bool,
    path: list[str] | None = None,
) -> ArgMismatchDetail | None:
    """Returns None if OK, else first mismatch detail (dot-path + values + reason)."""
    if path is None:
        path = []
    for k, v in expected.items():
        cur_path = [*path, k]
        if k not in actual:
            return ArgMismatchDetail(
                path=".".join(cur_path), expected=v, actual="<missing>", reason="missing_key"
            )
        av = actual[k]
        if isinstance(v, dict) and isinstance(av, dict):
            sub = _subset_args_check(v, av, eps, coerce_num, cur_path)
            if sub is not None:
                return sub
        elif not _coerce_equal(v, av, eps, coerce_num):
            return ArgMismatchDetail(
                path=".".join(cur_path), expected=v, actual=av, reason="value_diff"
            )
    return None


def _strict_args_match(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return expected == actual


def _parse_args_as_json(tool: Tool, index: int) -> dict[str, Any]:
    try:
        return json.loads(tool.input_raw)
    except json.JSONDecodeError as e:
        raise UnexpectedToolError(
            message=f"Bad actual input JSON for {tool.tool_name}: {e}",
            details={"index": index, "raw": tool.input_raw},
        ) from e


class ReplayToolExecutor(ToolExecutor):
    """
    Replays tool calls from a captured conversation.
    Enforces both call order and argument equality (deep compare).
    """

    def __init__(
        self,
        expected_calls: list[ExpectedCall],
        *,
        policy: DriftPolicy,
        models: list[str],
        platforms: list[str],
        tools: list[ToolDefinition],
    ):
        self._calls = expected_calls
        self._i = 0
        self._policy = policy
        self.drifts: list[DriftEvent] = []
        self.error_message = None
        self.models = models
        self.platforms = platforms
        self.tools = tools

    def _record_drift_event(self, event: DriftEvent) -> None:
        self.drifts.append(event)
        if len(self.drifts) > self._policy.max_events:
            self.error_message = "Drift budget exceeded."
            raise ReplayDriftError(
                message="Drift budget exceeded.",
                details={
                    "max_events": self._policy.max_events,
                    "drifts": [e.__dict__ for e in self.drifts],
                },
            )

    async def execute(self, tool: Tool) -> ToolExecutionResult:
        logger.info(f"Intercepted tool {tool.tool_name}")

        if self._i >= len(self._calls):
            evt = DriftEvent(
                index_before=self._i,
                drift_type=DriftType.EXTRA_ACTUAL_CALL,
                message=(
                    f"Unexpected tool call #{self._i + 1}: {tool.tool_name}. "
                    "No more calls were recorded."
                ),
                expected_tool=None,
                actual_tool=tool.tool_name,
            )
            self._record_drift_event(evt)
            self.error_message = "No more calls were recorded."
            raise ReplayDriftError(evt.message, {"event": evt.__dict__})

        exp = self._calls[self._i]

        if tool.tool_name != exp.tool_name:
            evt = DriftEvent(
                index_before=self._i,
                drift_type=DriftType.NAME_MISMATCH,
                message=(
                    f"Tool name mismatch at call #{self._i + 1}.\n"
                    f"  expected: {exp.tool_name}\n"
                    f"  got     : {tool.tool_name}"
                ),
                expected_tool=exp.tool_name,
                actual_tool=tool.tool_name,
                expected_args=exp.expected_args,
            )
            self._record_drift_event(evt)
            self.error_message = evt.message
            raise ReplayDriftError(evt.message, {"event": evt.__dict__})

        actual_args = _parse_args_as_json(tool, self._i)
        if not _strict_args_match(exp.expected_args, actual_args):
            evt = DriftEvent(
                index_before=self._i,
                drift_type=DriftType.ARG_MISMATCH,
                message=(
                    f"Arguments mismatch at call #{self._i + 1} for '{tool.tool_name}'.\n"
                    f"  expected args: {json.dumps(exp.expected_args, indent=2, sort_keys=True)}\n"
                    f"  got args     : {json.dumps(actual_args, indent=2, sort_keys=True)}"
                ),
                expected_tool=exp.tool_name,
                actual_tool=tool.tool_name,
                expected_args=exp.expected_args,
                actual_args=actual_args,
            )
            # Attempt repair by forgiving args (subset/epsilon/coercions)
            mismatch_args = _subset_args_check(
                exp.expected_args,
                actual_args,
                self._policy.numeric_epsilon,
                self._policy.coerce_json_number_like,
            )
            if self._policy.allow_arg_subset and mismatch_args:
                evt.repair_action = "FORGIVE_ARGS"
                evt.message = (
                    f"Non-strict arg mismatch at call #{self._i + 1} for '{tool.tool_name}'. "
                    f"Key '{mismatch_args.path}' expected value {mismatch_args.expected}, "
                    f"got {mismatch_args.actual}"
                )
                self._record_drift_event(evt)
            else:
                evt.repair_action = "FAILED"
                self._record_drift_event(evt)
                self.error_message = evt.message
                raise ReplayDriftError(evt.message, {"event": evt.__dict__})

        self._i += 1

        logger.info(f"Tool {tool.tool_name} mocked with stored results")
        return ToolExecutionResult(error=exp.error, output=json.dumps(exp.output))

    def finalize(self) -> None:
        if self._i >= len(self._calls):
            return  # nothing left

        remaining = self._calls[self._i :]
        summary = {
            "start_index": self._i,
            "count": len(remaining),
            "calls": [
                {"index": self._i + k, "tool": c.tool_name, "expected_args": c.expected_args}
                for k, c in enumerate(remaining)
            ],
        }

        remaining_names = [tool.tool_name for tool in remaining]
        evt = DriftEvent(
            index_before=self._i,
            drift_type=DriftType.LEFTOVER_RECORDED_CALLS,
            message=(
                f"{len(remaining)} recorded call(s) left unconsumed "
                f"at end of replay: {', '.join(remaining_names)}."
            ),
            expected_tool=remaining[0].tool_name if remaining else None,
            expected_args=remaining[0].expected_args if remaining else None,
        )

        if not self._policy.assert_all_consumed:
            evt.repair_action = "IGNORE_LEFTOVER_CALLS"

        self._record_drift_event(evt)

        if self._policy.assert_all_consumed:
            self.error_message = evt.message
            raise ReplayDriftError("Recorded calls remaining at end of replay.", details=summary)

        return

    @classmethod
    def from_conversation(cls, messages: list[ThreadMessage]) -> "ReplayToolExecutor":  # noqa: C901, PLR0912
        expected: list[ExpectedCall] = []
        models = set()
        platforms = set()
        tools_by_name: dict[str, ToolDefinition] = {}

        for msg in messages:
            for item in msg.content:
                if isinstance(item, ThreadToolUsageContent):
                    if item.sub_type not in {"action-external", "mcp-external"}:
                        continue
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

                tool_category = tool.get("category")
                tool_name = tool.get("name")

                if tool_category not in ["action-tool", "mcp-tool"]:
                    # No ops
                    continue

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
            policy=DriftPolicy(
                allow_arg_subset=False,
                numeric_epsilon=1e-6,
                coerce_json_number_like=True,
                max_events=20,
            ),
            models=sorted(models),
            platforms=sorted(platforms),
            tools=sorted(tools_by_name.values(), key=lambda tool: tool.name),
        )
