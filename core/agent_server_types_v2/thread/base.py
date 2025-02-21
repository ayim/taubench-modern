from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal, Self
from uuid import UUID, uuid4

from agent_server_types_v2.thread.content import (
    ThreadAttachmentContent,
    ThreadQuickActionsContent,
    ThreadTextContent,
    ThreadThoughtContent,
    ThreadToolUsageContent,
    ThreadVegaChartContent,
)

AnyThreadMessageContent = (
    ThreadTextContent
    | ThreadQuickActionsContent
    | ThreadVegaChartContent
    | ThreadToolUsageContent
    | ThreadThoughtContent
    | ThreadAttachmentContent
)


@dataclass
class ThreadMessage:
    """Base class for all messages in a thread."""

    content: list[AnyThreadMessageContent] = field(
        metadata={"description": "The contents of the thread message"},
    )
    """The contents of the thread message"""

    role: Literal["user", "agent"]
    """The role of the message sender."""

    commited: bool = field(
        default=False,
        metadata={
            "description": "Whether the message has been committed to the thread (saved to backing storage)",
        },
    )
    """Whether the message has been committed to the thread (saved to backing storage)"""

    created_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The time the message was created"},
    )
    """The time the message was created"""

    updated_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The time the message was last updated"},
    )
    """The time the message was last updated"""

    agent_metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": "The metadata associated with the message (for agent architecture use only)",
        },
    )
    """The metadata associated with the message (for agent architecture use only)"""

    server_metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": "The metadata associated with the message (for agent-server use only)",
        },
    )
    """The metadata associated with the message (for agent-server use only)"""

    message_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={"description": "The unique identifier for the message"},
    )
    """The unique identifier for the message"""

    @property
    def metadata(self) -> dict[str, Any]:
        """The metadata associated with the message. This is a read-only property that combines
        agent_metadata and server_metadata. Any attempts to modify the returned dictionary or its nested
        dictionaries will raise TypeError."""
        return MappingProxyType(
            {
                "agent": MappingProxyType(dict(self.agent_metadata)),
                "server": MappingProxyType(dict(self.server_metadata)),
            },
        )

    def copy(self) -> Self:
        """Returns a deep copy of the message.

        Preserves the uid, updated_at, and created_at.
        """
        from copy import deepcopy

        # Use the same class as `self`
        cls = type(self)

        new_message = cls(
            role=self.role,
            updated_at=self.updated_at,
            created_at=self.created_at,
            content=[c.model_copy() for c in self.content],
            agent_metadata=deepcopy(self.agent_metadata),
            server_metadata=deepcopy(self.server_metadata),
        )
        new_message.message_id = self.message_id
        return new_message

    def to_json_dict(self) -> dict:
        """Serializes the message to a dictionary. Useful for JSON serialization."""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": [content.model_dump() for content in self.content],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "agent_metadata": self.agent_metadata,
            "server_metadata": self.server_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Deserializes the message from a dictionary. Useful for JSON deserialization."""
        from agent_server_types_v2.thread.content import ThreadMessageContent

        if "message_id" in data and isinstance(data["message_id"], UUID):
            data["message_id"] = str(data["message_id"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "content" in data:
            data["content"] = [
                ThreadMessageContent.model_validate(content)
                for content in data["content"]
            ]
        return cls(**data)
