"""Live tool executor that invokes actual tool implementations during evals."""

import json
from typing import Any

import structlog

from agent_platform.core.evals.agent_client import (
    Tool,
    ToolExecutionResult,
    ToolExecutor,
    UnexpectedToolError,
)
from agent_platform.core.kernel import Kernel
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.tools.tool_execution_result import (
    ToolExecutionResult as KernelToolExecutionResult,
)

logger = structlog.get_logger(__name__)


def _kernel_result_to_client_result(result: KernelToolExecutionResult) -> ToolExecutionResult:
    try:
        output_payload = json.dumps(result.output_raw)
    except TypeError:
        logger.warning(
            "Live tool output not JSON serializable; coercing to string",
            tool=result.definition.name,
        )
        output_payload = json.dumps(str(result.output_raw))

    return ToolExecutionResult(error=result.error, output=output_payload)


class LiveToolExecutor(ToolExecutor):
    """Executes tools against live implementations instead of replaying outputs."""

    def __init__(self, tools: list[ToolDefinition]):
        self.tools = tools
        self._kernel: Kernel | None = None
        self._tool_by_name: dict[str, ToolDefinition] = {}
        self.drifts: list[Any] = []
        for definition in tools:
            if definition.name in self._tool_by_name:
                logger.warning(
                    "Overwriting duplicate tool definition for live executor",
                    tool=definition.name,
                )
            self._tool_by_name[definition.name] = definition

    def attach_kernel(self, kernel: Kernel) -> None:
        self._kernel = kernel

    async def execute(self, tool: Tool) -> ToolExecutionResult:
        if self._kernel is None:
            raise UnexpectedToolError(
                message="Live tool execution requested but kernel not attached",
                details={"tool": tool.tool_name},
            )

        definition = self._tool_by_name.get(tool.tool_name)
        if definition is None:
            raise UnexpectedToolError(
                message="Cannot find live tool definition",
                details={"tool": tool.tool_name},
            )

        pending_tool_calls = [
            (
                definition,
                ResponseToolUseContent(
                    tool_call_id=tool.tool_call_id,
                    tool_name=tool.tool_name,
                    tool_input_raw=tool.input_raw,
                ),
            )
        ]

        results: list[KernelToolExecutionResult] = []
        async for kernel_result in self._kernel.tools.execute_pending_tool_calls(
            pending_tool_calls
        ):
            results.append(kernel_result)

        if not results:
            raise UnexpectedToolError(
                message="Live tool execution produced no result",
                details={"tool": tool.tool_name},
            )

        return _kernel_result_to_client_result(results[0])

    def finalize(self) -> None:
        return None


__all__ = ["LiveToolExecutor"]
