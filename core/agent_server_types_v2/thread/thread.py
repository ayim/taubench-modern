from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from agent_server_types_v2.thread.base import ThreadMessage


@dataclass
class Thread:
    """Represents an entire conversation (thread) consisting of multiple messages
    with multiple content types (text, tool usage, vega chart, etc.) nested within
    each message.

    Thread is a key concept and DISTINCT from PromptMessage (even if there is a
    structural similarity). The result of an LLM call may end up as (part) of a message
    in a thread; and, similarly, content in a ThreadMessage (or many messages) may be
    converted and used in PromptMessages to pass to an LLM. But, for the sake of
    clarity, we have kept seperate distinct types for ThreadMessages and
    PromptMessages.
    """

    user_id: str = field(
        metadata={"description": "The user ID of the user who created this thread."},
    )
    """The user ID of the user who created this thread."""

    agent_id: str = field(
        metadata={"description": "The agent ID of the agent that created this thread."},
    )
    """The agent ID of the agent that created this thread."""

    name: str = field(metadata={"description": "The name of this thread."})
    """The name of this thread."""

    thread_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={"description": "A unique ID for this thread."},
    )
    """A unique ID for this thread."""

    messages: list[ThreadMessage] = field(
        default_factory=list, metadata={"description": "All messages in this thread."},
    )
    """All messages in this thread."""

    created_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "When this thread was created."},
    )
    """When this thread was created."""

    updated_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "When this thread was last updated."},
    )
    """When this thread was last updated."""

    metadata: dict = field(
        default_factory=dict,
        metadata={"description": "Arbitrary thread-level metadata."},
    )
    """Arbitrary thread-level metadata."""

    def add_message(self, message: ThreadMessage) -> None:
        """Adds a new message to the thread.  Updates `updated_at` to reflect
        that the thread has changed.
        """
        self.messages.append(message)
        self.updated_at = datetime.now()

    def find_message(self, message_id: str) -> ThreadMessage | None:
        """Helper to locate a message by its UID.  Returns None if not found."""
        for msg in self.messages:
            if msg.message_id == message_id:
                return msg
        return None

    def copy(self) -> Self:
        """Returns a deep copy of the thread."""
        return Thread(
            user_id=self.user_id,
            agent_id=self.agent_id,
            name=self.name,
            thread_id=self.thread_id,
            messages=[msg.copy() for msg in self.messages],
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=self.metadata,
        )

    def to_json_dict(self) -> dict:
        """Serializes the thread to a dictionary.  Useful for JSON serialization."""
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "messages": [msg.to_json_dict() for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Thread":
        """Create a thread from a dictionary."""
        data = data.copy()
        messages = [
            ThreadMessage.from_dict(msg) if isinstance(msg, dict) else msg
            for msg in data.pop("messages", [])
        ]
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data, messages=messages)
