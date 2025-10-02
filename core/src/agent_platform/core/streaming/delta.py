from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors import ErrorResponse

StreamingDeltaType = Literal[
    "agent_ready",
    "agent_finished",
    "agent_error",
    "message_content",
    "message_metadata",
    "message_begin",
    "message_end",
    "request_user_input",
    "request_tool_execution",
    "thread_name_updated",
]


@dataclass(frozen=True)
class StreamingDelta:
    """Type representing a streaming delta."""

    timestamp: datetime = field(metadata={"description": "The timestamp of the delta."})
    """The timestamp of the delta."""
    event_type: StreamingDeltaType = field(
        metadata={"description": "The type of streaming event."},
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
        }


@dataclass(frozen=True)
class StreamingDeltaRequestUserInput(StreamingDelta):
    """Type representing a streaming delta to request user input."""

    message: str = field(metadata={"description": "The message to request user input."})
    """The message to request user input."""
    timeout: float = field(metadata={"description": "The timeout for the user input."})
    """The timeout for the user input."""

    event_type: Literal["request_user_input"] = field(
        metadata={"description": "The type of streaming event."},
        default="request_user_input",
        init=False,
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "message": self.message,
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class StreamingDeltaAgent(StreamingDelta):
    """Type representing a streaming delta for an agent."""

    run_id: str = field(metadata={"description": "The ID of the run."})
    """The ID of the run."""
    thread_id: str = field(metadata={"description": "The ID of the thread."})
    """The ID of the thread."""
    agent_id: str = field(metadata={"description": "The ID of the agent."})
    """The ID of the agent."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
        }


@dataclass(frozen=True)
class StreamingDeltaAgentReady(StreamingDeltaAgent):
    """Type representing a streaming delta to indicate that the agent is ready."""

    event_type: Literal["agent_ready"] = field(
        metadata={"description": "The type of streaming event."},
        default="agent_ready",
        init=False,
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
        }


@dataclass(frozen=True)
class StreamingDeltaAgentFinished(StreamingDeltaAgent):
    """Type representing a streaming delta to indicate that the agent is finished."""

    event_type: Literal["agent_finished"] = field(
        metadata={"description": "The type of streaming event."},
        default="agent_finished",
        init=False,
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
        }


@dataclass(frozen=True)
class StreamingDeltaAgentError(StreamingDeltaAgent):
    """Type representing a streaming delta to indicate that
    the agent is in an error state."""

    error: ErrorResponse = field(
        metadata={"description": "The error information in the agreed upon error response."}
    )
    """The error information following the agreed upon error response."""

    event_type: Literal["agent_error"] = field(
        metadata={"description": "The type of streaming event."},
        default="agent_error",
        init=False,
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "error": self.error.model_dump(mode="json"),
        }


@dataclass(frozen=True)
class StreamingDeltaMessage(StreamingDelta):
    """Type representing a streaming delta for a message."""

    sequence_number: int = field(
        metadata={"description": "The sequence number of the delta."},
    )
    """The sequence number of the delta."""
    message_id: str = field(metadata={"description": "The message ID."})
    """The message ID."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "sequence_number": self.sequence_number,
            "message_id": self.message_id,
        }


@dataclass(frozen=True)
class StreamingDeltaMessageContent(StreamingDeltaMessage):
    """Type representing a streaming delta update to message content."""

    delta: GenericDelta = field(
        metadata={"description": "The delta to apply to the message content."},
    )
    """The delta to apply to the message content."""
    event_type: Literal["message_content"] = field(
        metadata={
            "description": "The type of streaming event.(Always 'message_content' for this type.)",
        },
        default="message_content",
        init=False,
    )
    """The type of streaming event. (Always 'message_content' for this type.)"""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "delta": self.delta.model_dump(),
        }


@dataclass(frozen=True)
class StreamingDeltaMessageBegin(StreamingDeltaMessage):
    """Type representing a streaming delta to demark the beginning of a message."""

    thread_id: str = field(metadata={"description": "The ID of the thread."})
    """The ID of the thread."""
    agent_id: str = field(
        metadata={"description": "The ID of the agent attached to this thread."},
    )
    """The ID of the agent attached to this thread."""
    data: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Any extra metadata to begin the stream with."},
    )
    """Any extra metadata to begin the stream with."""
    channel: Literal["events"] = field(
        metadata={
            "description": "The channel for this delta.(Always 'events' for this type.)",
        },
        default="events",
        init=False,
    )
    """The channel for this delta. (Always 'events' for this type.)"""
    event_type: Literal["message_begin"] = field(
        metadata={
            "description": "The type of streaming event.(Always 'message_begin' for this type.)",
        },
        default="message_begin",
        init=False,
    )
    """The type of streaming event. (Always 'message_begin' for this type.)"""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "data": self.data,
        }


@dataclass(frozen=True)
class StreamingDeltaMessageEnd(StreamingDeltaMessage):
    """Type representing a streaming delta to demark the ending of a message."""

    thread_id: str = field(metadata={"description": "The ID of the thread."})
    """The ID of the thread."""
    agent_id: str = field(
        metadata={"description": "The ID of the agent attached to this thread."},
    )
    """The ID of the agent attached to this thread."""
    data: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Any extra metadata to end the stream with."},
    )
    """Any extra metadata to end the stream with."""
    channel: Literal["events"] = field(
        metadata={
            "description": "The channel for this delta.(Always 'events' for this type.)",
        },
        default="events",
    )
    """The channel for this delta. (Always 'events' for this type.)"""
    event_type: Literal["message_end"] = field(
        metadata={
            "description": "The type of streaming event.(Always 'message_end' for this type.)",
        },
        default="message_end",
        init=False,
    )
    """The type of streaming event. (Always 'message_end' for this type.)"""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "data": self.data,
        }


@dataclass(frozen=True)
class StreamingDeltaRequestToolExecution(StreamingDelta):
    """Request that the client execute a tool.

    Some client tools may _not_ need to block for the client to return a
    result (these are "...").
    """

    tool_name: str = field(metadata={"description": "Name of the tool."})
    tool_call_id: str = field(metadata={"description": "Tool call identifier."})
    input_raw: str = field(metadata={"description": "Raw JSON string inputs."})
    input_parsed: dict[str, Any] | None = field(
        metadata={"description": "Parsed JSON inputs; may be None if the input_raw is not JSON."},
        default=None,
    )
    """Parsed JSON inputs; may be None if the input_raw is not JSON."""
    requires_execution: bool = field(
        metadata={"description": "Whether the client must execute the tool and return a result."},
        default=True,
    )
    """Whether the client must execute the tool and return a result."""

    event_type: Literal["request_tool_execution"] = field(
        metadata={"description": "The type of streaming event."},
        default="request_tool_execution",
        init=False,
    )

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "input_raw": self.input_raw,
        }


@dataclass(frozen=True)
class StreamingDeltaThreadNameUpdated(StreamingDelta):
    """Notify clients that a thread has been updated (e.g., renamed).

    This is emitted for non-message updates that should be reflected in the UI
    without requiring a separate GET request.
    """

    thread_id: str = field(metadata={"description": "The ID of the thread."})
    agent_id: str = field(metadata={"description": "The ID of the agent."})
    new_name: str = field(metadata={"description": "The new name of the thread."})
    old_name: str | None = field(
        default=None, metadata={"description": "The previous name of the thread, if known."}
    )
    reason: Literal["auto", "manual"] = field(
        default="manual", metadata={"description": "Reason for the update."}
    )

    event_type: Literal["thread_name_updated"] = field(
        metadata={"description": "The type of streaming event."},
        default="thread_name_updated",
        init=False,
    )

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "new_name": self.new_name,
            "old_name": self.old_name,
            "reason": self.reason,
        }
