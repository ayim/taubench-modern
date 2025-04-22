from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import uuid4

from agent_platform.core.thread import ThreadMessage


@dataclass
class AddThreadMessagePayload(ThreadMessage):
    """Payload for adding a message to a thread."""

    user_id: str = field(
        init=False,
        repr=False,
        metadata={"description": "The ID of the user that owns the thread."},
    )
    """The ID of the user that owns the thread."""

    thread_id: str = field(
        init=False,
        repr=False,
        metadata={"description": "The ID of the thread to add the message to."},
    )
    """The ID of the thread to add the message to."""

    message_id: str = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The ID of the message."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The ID of the message."""

    created_at: datetime = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The time the message was created."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The time the message was created."""

    updated_at: datetime = field(  # type: ignore
        init=False,
        repr=False,
        metadata={"description": "The time the message was last updated."},
    )
    # Intentionally overriden without a default value (to ensure it's set
    # in the payload)
    """The time the message was last updated."""

    @classmethod
    def to_thread_message(
        cls,
        payload: Self,
    ) -> ThreadMessage:
        return ThreadMessage(
            message_id=str(uuid4()),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            role=payload.role,
            content=payload.content,
            commited=payload.commited,
            agent_metadata=payload.agent_metadata,
            server_metadata=payload.server_metadata,
        )
