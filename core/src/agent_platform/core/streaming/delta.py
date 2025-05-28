from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from agent_platform.core.delta import GenericDelta

StreamingDeltaType = Literal[
    "agent_ready",
    "agent_finished",
    "agent_error",
    "message_content",
    "message_metadata",
    "message_begin",
    "message_end",
    "request_user_input",
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

    error_message: str = field(metadata={"description": "The error message."})
    """The error message."""
    error_stack_trace: str = field(metadata={"description": "The error stack trace."})
    """The error stack trace."""
    event_type: Literal["agent_error"] = field(
        metadata={"description": "The type of streaming event."},
        default="agent_error",
        init=False,
    )
    """The type of streaming event."""

    def model_dump(self) -> dict[str, Any]:
        return {
            **super().model_dump(),
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
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
