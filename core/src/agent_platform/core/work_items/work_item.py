from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.base import ThreadMessage


class WorkItemStatus(StrEnum):
    """The status of a work item."""

    CANCELLED = "CANCELLED"
    """The work item has been cancelled."""

    COMPLETED = "COMPLETED"
    """The work item has been completed."""

    ERROR = "ERROR"
    """The work item has errored."""

    EXECUTING = "EXECUTING"
    """The work item is being executed."""

    NEEDS_REVIEW = "NEEDS_REVIEW"
    """The work item needs review."""

    PENDING = "PENDING"
    """The work item is pending."""


@dataclass
class WorkItem:
    """REST API representation of a work item."""

    work_item_id: str = field(
        metadata={"description": "The unique identifier for the work item"},
    )
    """The unique identifier for the work item."""

    user_id: str = field(
        metadata={"description": "The ID of the user that created this work item"},
    )
    """The ID of the user that created this work item."""

    agent_id: str = field(
        metadata={"description": "The ID of the agent that will process this work item"},
    )
    """The ID of the agent that will process this work item."""

    thread_id: str | None = field(
        default=None,
        metadata={
            "description": (
                "The ID of the thread associated with this work item (may be null until created)."
            ),
        },
    )
    """The ID of the thread associated with this work item (nullable)."""

    status: WorkItemStatus = field(
        default=WorkItemStatus.PENDING,
        metadata={"description": "The status of the work item"},
    )
    """The status of the work item."""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp when the work item was created"},
    )
    """The timestamp when the work item was created."""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp when the work item was last updated"},
    )
    """The timestamp when the work item was last updated."""

    completed_by: str | None = field(
        default=None,
        metadata={"description": "The ID of the user who completed the work item"},
    )
    """The ID of the user who completed the work item."""

    status_updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp when the work item status was last updated"},
    )
    """The timestamp when the work item status was last updated."""

    status_updated_by: str = field(
        default="SYSTEM",
        metadata={"description": "The ID of the user who last updated the work item status"},
    )
    """The ID of the user who last updated the work item status."""

    messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "The messages in the work item conversation"},
    )
    """The messages in the work item conversation."""

    payload: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The payload of the work item"},
    )
    """The payload of the work item."""

    def model_dump(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "user_id": self.user_id,
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

    def to_initiate_stream_payload(self) -> InitiateStreamPayload:
        return InitiateStreamPayload(
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            name=f"Work Item {self.work_item_id}",
            messages=self.messages,
            metadata={
                "from_work_item": True,
                "work_item_id": self.work_item_id,
            },
        )

    @classmethod
    def model_validate(cls, data: dict) -> "WorkItem":
        data = data.copy()

        # Handle UUIDs
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        if "work_item_id" in data and isinstance(data["work_item_id"], UUID):
            data["work_item_id"] = str(data["work_item_id"])

        # Parse nested objects
        if "status" in data and isinstance(data["status"], str):
            data["status"] = WorkItemStatus(data["status"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "status_updated_at" in data and isinstance(data["status_updated_at"], str):
            data["status_updated_at"] = datetime.fromisoformat(data["status_updated_at"])
        if "messages" in data:
            data["messages"] = [
                ThreadMessage.model_validate(msg) if isinstance(msg, dict) else msg
                for msg in data["messages"]
            ]

        return cls(**data)
