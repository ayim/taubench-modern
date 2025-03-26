from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from agent_server_types_v2.thread import Thread


@dataclass
class InitiateStreamPayload(Thread):
    """Payload for initiating a stream against a thread."""

    user_id: str = field(
        init=False, repr=False,
        metadata={"description": "The ID of the user that owns the thread."},
    )
    """The ID of the user that owns the thread."""

    created_at: datetime = field(
        init=False, repr=False,
        metadata={"description": "The time the thread was created."},
    )
    """The time the thread was created."""

    updated_at: datetime = field(
        init=False, repr=False,
        metadata={"description": "The time the thread was last updated."},
    )
    """The time the thread was last updated."""

    thread_id: str | None = field(
        default=None,
        metadata={"description": "The ID of the thread to stream against."},
    )
    """The ID of the thread to stream against."""

    name: str | None = field(
        default=None,
        metadata={"description": "The name of the thread to stream against."},
    )
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
    def to_thread(cls, payload: Self, user_id: str) -> Thread:
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
            created_at=datetime.now(),
            updated_at=datetime.now(),
            messages=[],
            metadata={},
        )
