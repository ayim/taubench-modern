from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

IncomingDeltaType = Literal[
    "client_tool_result",
    "user_input",
]


@dataclass(frozen=True)
class IncomingDelta:
    """Type representing a streaming delta."""

    timestamp: datetime = field(metadata={"description": "The timestamp of the delta."})
    """The timestamp of the delta."""
    event_type: IncomingDeltaType = field(metadata={"description": "The type of incoming event."})


@dataclass(frozen=True)
class IncomingDeltaClientToolResult(IncomingDelta):
    """Type representing a client tool result."""

    tool_call_id: str = field(metadata={"description": "The tool call ID."})
    """The tool call ID."""
    result: dict[str, Any] = field(metadata={"description": "The result of the tool call."})
    """The result of the tool call."""

    event_type: Literal["client_tool_result"] = field(
        metadata={"description": "The type of incoming event."},
        default="client_tool_result",
        init=False,
    )
    """The type of incoming event."""


@dataclass(frozen=True)
class IncomingDeltaUserInput(IncomingDelta):
    """Type representing a user input."""

    input: str = field(metadata={"description": "The user input."})
    """The user input."""

    event_type: Literal["user_input"] = field(
        metadata={"description": "The type of incoming event."},
        default="user_input",
        init=False,
    )
    """The type of incoming event."""
