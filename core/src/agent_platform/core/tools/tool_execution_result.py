"""ToolExecutionResult: represents the result of a tool execution."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass
class ToolExecutionResult:
    """Represents the result of a tool execution."""

    definition: ToolDefinition = field(
        metadata={"description": "The definition of the tool that was executed"},
    )
    """The definition of the tool that was executed"""

    tool_call_id: str = field(
        metadata={"description": "The unique identifier of the tool call"},
    )
    """The unique identifier of the tool call"""

    execution_id: str = field(
        metadata={"description": "The unique identifier of the tool execution"},
    )
    """The unique identifier of the tool execution"""

    input_raw: str = field(
        metadata={"description": "The raw input of the tool that was executed"},
    )
    """The raw input of the tool that was executed"""

    _input_parsed: dict[str, Any] = field(
        init=False,
        metadata={"description": "The parsed input of the tool that was executed"},
    )
    """The parsed input of the tool that was executed"""

    output_raw: Any | None = field(
        metadata={"description": "The raw output of the tool that was executed"},
    )
    """The raw output of the tool that was executed"""

    error: str | None = field(
        metadata={"description": "The error that occurred during the tool execution"},
    )
    """The error that occurred during the tool execution"""

    execution_started_at: datetime = field(
        metadata={"description": "The timestamp when the tool execution started"},
    )
    """The timestamp when the tool execution started"""

    execution_ended_at: datetime = field(
        metadata={"description": "The timestamp when the tool execution ended"},
    )
    """The timestamp when the tool execution ended"""

    execution_metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The metadata of the tool execution"},
    )
    """The metadata of the tool execution"""

    action_server_run_id: str | None = field(
        default=None,
        metadata={"description": "The remote run ID from the action server"},
    )
    """The remote run ID from the action server"""

    def __post_init__(self) -> None:
        """Validates and processes the tool input after initialization.

        Ensures the type field is valid and converts string inputs to dictionaries.
        """
        if isinstance(self.input_raw, str):
            # Need to use setattr in a frozen dataclass
            # so we can't use the property here
            self._input_parsed = json.loads(self.input_raw)
        else:
            self._input_parsed = self.input_raw

    @property
    def input(self) -> dict[str, Any]:
        """Returns the tool input as a dictionary.

        This property ensures that the tool input is always a dictionary,
        even if it was originally provided as a string.
        """
        return self._input_parsed

    def inject_system_feedback(self, feedback: str) -> None:
        """Injects system feedback into the tool execution result."""
        # TODO: hard to suss out in benchmarking how much this really helps
        # even if the idea is intuitive enough
        if self.output_raw and "important_system_feedback" in self.output_raw:
            self.output_raw["important_system_feedback"] += "\n" + feedback
            return
        self.output_raw = {
            "important_system_feedback": feedback,
            "original_result": self.output_raw,
        }
