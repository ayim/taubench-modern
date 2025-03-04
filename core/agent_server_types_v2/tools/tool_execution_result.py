"""ToolExecutionResult: represents the result of a tool execution."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent_server_types_v2.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class ToolExecutionResult:
    """Represents the result of a tool execution."""

    definition: ToolDefinition = field(
        metadata={"description": "The definition of the tool that was executed"},
    )
    """The definition of the tool that was executed"""

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

    output_raw: str = field(
        metadata={"description": "The raw output of the tool that was executed"},
    )
    """The raw output of the tool that was executed"""

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

    def __post_init__(self) -> None:
        """Validates and processes the tool input after initialization.

        Ensures the type field is valid and converts string inputs to dictionaries.
        """
        if isinstance(self.input_raw, str):
            # Need to use setattr in a frozen dataclass
            # so we can't use the property here
            object.__setattr__(self, "_input_parsed", json.loads(self.input_raw))
        else:
            object.__setattr__(self, "_input_parsed", self.input_raw)

    @property
    def input(self) -> dict[str, Any]:
        """Returns the tool input as a dictionary.

        This property ensures that the tool input is always a dictionary,
        even if it was originally provided as a string.
        """
        return self._input_parsed
