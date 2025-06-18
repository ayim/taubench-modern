from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self


class WorkItemStatus(StrEnum):
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    EXECUTING = "EXECUTING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    PENDING = "PENDING"


@dataclass
class WorkItemMessageContent:
    """The content of a message in a work item conversation."""

    kind: Literal["text"]
    text: str
    file_name: str | None = None
    mime_type: str | None = None

    def model_dump(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
        }


@dataclass
class WorkItemMessage:
    """A message in a work item conversation."""

    role: Literal["user", "agent"]
    content: list[WorkItemMessageContent]

    @classmethod
    def model_validate(cls, data: dict) -> Self:
        """Create a WorkItemMessage from a dictionary, recursively initializing content."""
        data = data.copy()

        # Convert content dictionaries to WorkItemMessageContent objects
        if "content" in data and isinstance(data["content"], list):
            data["content"] = [
                WorkItemMessageContent(**item) if isinstance(item, dict) else item
                for item in data["content"]
            ]

        return cls(**data)

    def model_dump(self) -> dict:
        return {
            "role": self.role,
            "content": [item.model_dump() for item in self.content],
        }


@dataclass
class CreateWorkItemPayload:
    """Payload to create a work item."""

    agent_id: str
    messages: list[WorkItemMessage] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkItem:
    """REST API representation of a work item."""

    work_item_id: str
    agent_id: str
    thread_id: str
    status: str = WorkItemStatus.PENDING.value
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_by: str | None = None
    status_updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status_updated_by: str = "SYSTEM"
    messages: list[WorkItemMessage] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_by": self.completed_by,
            "status_updated_at": self.status_updated_at.isoformat(),
            "status_updated_by": self.status_updated_by,
            "messages": [msg.model_dump() for msg in self.messages],
            "payload": self.payload,
        }

    @classmethod
    def model_validate(cls, data: dict) -> Self:
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "status_updated_at" in data and isinstance(data["status_updated_at"], str):
            data["status_updated_at"] = datetime.fromisoformat(data["status_updated_at"])
        if "messages" in data:
            from agent_platform.core.thread.base import ThreadMessage

            data["messages"] = [
                ThreadMessage.model_validate(msg) if isinstance(msg, dict) else msg
                for msg in data["messages"]
            ]
        return cls(**data)
