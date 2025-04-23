from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from agent_platform.core.thread import Thread, ThreadMessage


@dataclass
class InitiateStreamPayload(Thread):
    """Payload for initiating a stream against a thread."""

    user_id: str = field(
        init=False,
        repr=False,
        metadata={"description": "The ID of the user that owns the thread."},
    )
    """The ID of the user that owns the thread."""

    created_at: datetime = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The time the thread was created."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The time the thread was created."""

    updated_at: datetime = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The time the thread was last updated."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The time the thread was last updated."""

    thread_id: str | None = field(  # type: ignore
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
            metadata={},
        )

    @classmethod
    def model_validate(cls, data: Any) -> "InitiateStreamPayload":
        return InitiateStreamPayload(
            agent_id=data["agent_id"],
            name=data["name"] if "name" in data else None,
            thread_id=data["thread_id"] if "thread_id" in data else None,
            messages=[
                ThreadMessage.model_validate(message) for message in data["messages"]
            ],
            metadata=data["metadata"] if "metadata" in data else {},
        )
