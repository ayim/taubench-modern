from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import uuid4

from agent_platform.core.thread import Thread


@dataclass
class UpsertThreadPayload(Thread):
    """Payload for upserting a thread."""

    user_id: str = field(
        init=False,
        repr=False,
        metadata={"description": "The ID of the user that owns the thread."},
    )
    """The ID of the user that owns the thread."""

    thread_id: str = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The ID of the thread."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The ID of the thread."""

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
        metadata={"description": "The last time the thread was updated."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The last time the thread was updated."""

    @classmethod
    def to_thread(cls, payload: Self, user_id: str) -> Thread:
        return Thread(
            user_id=user_id,
            thread_id=str(uuid4()),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            name=payload.name,
            agent_id=payload.agent_id,
            messages=payload.messages,
            metadata=payload.metadata,
            trial_id=payload.trial_id,
            work_item_id=payload.work_item_id,
        )
