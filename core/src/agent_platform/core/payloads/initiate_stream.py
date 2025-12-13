from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.tools.tool_definition import ToolCategory, ToolDefinition


@dataclass(frozen=True)
class ToolDefinitionPayload:
    """Represents the definition of a tool."""

    name: str = field(metadata={"description": "The name of the tool"})
    """The name of the tool"""

    description: str = field(metadata={"description": "The description of the tool"})
    """The description of the tool"""

    input_schema: dict[str, Any] = field(
        metadata={"description": "The schema of the tool input"},
    )
    """The schema of the tool input"""

    category: ToolCategory = field(
        metadata={"description": "The category of the tool"},
        default="unknown",
    )
    """The category of the tool"""

    @classmethod
    def model_validate(cls, data: dict) -> "ToolDefinitionPayload":
        """Validate and convert a dictionary into a ToolDefinition instance."""
        return cls(
            name=data["name"],
            description=data["description"],
            input_schema=data["input_schema"],
            category=data.get("category", "unknown"),
        )

    def to_tool_definition(
        self,
    ) -> ToolDefinition:
        return ToolDefinition(
            category=self.category,
            description=self.description,
            input_schema=self.input_schema,
            name=self.name,
            function=lambda *a, **k: None,
        )


@dataclass(frozen=True)
class InitiateStreamPayload:
    """Payload for initiating a stream against a thread."""

    agent_id: str = field(
        metadata={"description": "The agent ID of the agent that created this thread."},
    )
    """The agent ID of the agent that created this thread."""

    thread_id: str | None = field(
        default=None,
        metadata={"description": "The ID of the thread to stream against."},
    )
    # Intentionally overriden to be optional in the payload
    """The ID of the thread to stream against."""

    name: str | None = field(  # type: ignore
        default=None,
        metadata={"description": "The name of the thread to stream against."},
    )
    # Intentionally overriden to be optional in the payload
    """The name of the thread to stream against."""

    messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "All messages in this thread."},
    )
    """All messages in this thread."""

    metadata: dict = field(
        default_factory=dict,
        metadata={"description": "Arbitrary thread-level metadata."},
    )
    """Arbitrary thread-level metadata."""

    client_tools: list[ToolDefinitionPayload] = field(
        default_factory=list,
        metadata={"description": "The tools attached to the payload from an external client."},
    )
    """The tools attached to the payload from an external client."""

    override_model_id: str | None = field(
        default=None,
        metadata={"description": "The generic model ID to override the selection process with."},
    )
    """The generic model ID to override the selection process with."""

    def __post_init__(self) -> None:
        # Either the thread_id or the name must be provided
        if self.thread_id is None and self.name is None:
            raise ValueError("Either the thread_id or the name must be provided.")

        # Make sure the agent_id is a valid UUID
        try:
            UUID(self.agent_id)
        except ValueError as e:
            raise ValueError("The agent_id must be a valid UUID.") from e

        # Make sure the thread_id is a valid UUID (if provided)
        if self.thread_id is not None:
            try:
                UUID(self.thread_id)
            except ValueError as e:
                raise ValueError("The thread_id must be a valid UUID.") from e

        # Ensure all messages are complete (they must be provided in full,
        # no "streaming" of input messages)
        for message in self.messages:
            message.mark_complete()

    @classmethod
    def to_thread(cls, payload: "InitiateStreamPayload", user_id: str) -> Thread:
        # Make sure the user_id is a valid UUID
        try:
            UUID(user_id)
        except ValueError as e:
            raise ValueError("The user_id must be a valid UUID.") from e

        return Thread(
            user_id=user_id,
            agent_id=payload.agent_id,
            name=payload.name or "New Thread",
            thread_id=payload.thread_id or str(uuid4()),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            messages=payload.messages,
            metadata=payload.metadata,
        )

    @classmethod
    def model_validate(cls, data: Any) -> "InitiateStreamPayload":
        return InitiateStreamPayload(
            agent_id=data["agent_id"],
            name=data["name"] if "name" in data else None,
            thread_id=data["thread_id"] if "thread_id" in data else None,
            messages=[ThreadMessage.model_validate(message) for message in data["messages"]],
            metadata=data["metadata"] if "metadata" in data else {},
            client_tools=[ToolDefinitionPayload.model_validate(tool) for tool in data.get("client_tools", [])],
            override_model_id=data["override_model_id"] if "override_model_id" in data else None,
        )
