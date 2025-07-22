from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
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

    INDETERMINATE = "INDETERMINATE"
    """The outcome of the work item could not be determined by the agent evaluator."""

    PENDING = "PENDING"
    """The work item is pending."""

    PRECREATED = "PRECREATED"
    """The work item is is partially created to allow for file attachments."""


class WorkItemStatusUpdatedBy(StrEnum):
    """The user who last updated the work item status."""

    SYSTEM = "SYSTEM"
    """The system last updated the work item status."""

    AGENT = "AGENT"
    """The agent last updated the work item status."""

    HUMAN = "HUMAN"
    """A human last updated the work item status."""


class WorkItemCompletedBy(StrEnum):
    """The user who completed the work item."""

    AGENT = "AGENT"
    """The agent completed the work item."""

    HUMAN = "HUMAN"
    """A human completed the work item."""

    def as_status_updated_by(self) -> WorkItemStatusUpdatedBy:
        match self:
            case WorkItemCompletedBy.HUMAN:
                return WorkItemStatusUpdatedBy.HUMAN
            case WorkItemCompletedBy.AGENT:
                return WorkItemStatusUpdatedBy.AGENT
            case _:
                return WorkItemStatusUpdatedBy.SYSTEM


# Define a subset of workitem statuses that we allow for callbacks.
allowed_callback_status_types = Literal[
    WorkItemStatus.COMPLETED,
    WorkItemStatus.ERROR,
    WorkItemStatus.NEEDS_REVIEW,
    WorkItemStatus.CANCELLED,
    WorkItemStatus.INDETERMINATE,
]
allowed_callback_statuses = (
    WorkItemStatus.COMPLETED,
    WorkItemStatus.ERROR,
    WorkItemStatus.NEEDS_REVIEW,
    WorkItemStatus.CANCELLED,
    WorkItemStatus.INDETERMINATE,
)


@dataclass
class WorkItemCallback:
    """Payload to define callback after a work item reaches a certain status."""

    url: str = field(
        metadata={
            "description": "The URL to call (POST) when the work item reaches the specified status."
        },
    )
    """The URL to call (POST) when the work item reaches the specified status."""

    signature_secret: str | None = field(
        default=None,
        metadata={
            "description": "The secret to use to sign the callback payload."
            " If not provided, the callback will not be signed."
        },
    )
    """The secret to use to sign the callback payload. If not provided,
    the callback will not be signed."""

    on_status: allowed_callback_status_types = field(
        default=WorkItemStatus.NEEDS_REVIEW,
        metadata={
            "description": "The status which, when reached, will trigger"
            " the callback (default NEEDS_REVIEW)."
        },
    )
    """The status which, when reached, will trigger the callback."""

    def __post_init__(self):
        if self.on_status not in allowed_callback_statuses:
            raise ValueError(f"Calbacks can only be registered on: {allowed_callback_statuses}")

    def model_dump(self) -> dict:
        return {
            "url": self.url,
            "signature_secret": self.signature_secret,
            "on_status": self.on_status.value,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "WorkItemCallback":
        data = data.copy()

        # Parse on_status if it's a string
        if "on_status" in data and isinstance(data["on_status"], str):
            data["on_status"] = WorkItemStatus(data["on_status"])

        return cls(**data)


@dataclass
class WorkItemCallbackPayload:
    """Payload to define callback after a work item reaches a certain status."""

    work_item_id: str = field(
        metadata={"description": "The unique identifier for the work item"},
    )
    """The unique identifier for the work item."""

    agent_id: str = field(
        metadata={"description": "The unique identifier for the agent"},
    )
    """The unique identifier for the agent."""

    thread_id: str = field(
        metadata={"description": "The unique identifier for the thread"},
    )
    """The unique identifier for the thread."""

    status: WorkItemStatus = field(
        metadata={"description": "The status of the work item"},
    )
    """The status of the work item."""

    work_item_url: str = field(
        metadata={"description": "The URL of the work item"},
    )
    """The URL of the work item."""

    agent_name: str = field(
        metadata={"description": "The name of the agent"},
    )
    """The name of the agent."""

    def model_dump(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "status": self.status.value,
            "work_item_url": self.work_item_url,
            "agent_name": self.agent_name,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "WorkItemCallbackPayload":
        data = data.copy()

        if not data.get("work_item_id"):
            raise ValueError("work_item_id is required")
        if not data.get("agent_id"):
            raise ValueError("agent_id is required")
        if not data.get("thread_id"):
            raise ValueError("thread_id is required")
        if not data.get("work_item_url"):
            raise ValueError("work_item_url is required")
        if not data.get("agent_name"):
            raise ValueError("agent_name is required")

        # Parse status if it's a string
        if "status" in data and isinstance(data["status"], str):
            data["status"] = WorkItemStatus(data["status"])

        return cls(**data)


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

    agent_id: str | None = field(
        default=None,
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

    completed_by: WorkItemCompletedBy | None = field(
        default=None,
        metadata={"description": "The type of user who completed the work item"},
    )
    """The type of user who completed the work item."""

    status_updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp when the work item status was last updated"},
    )
    """The timestamp when the work item status was last updated."""

    status_updated_by: WorkItemStatusUpdatedBy = field(
        default=WorkItemStatusUpdatedBy.HUMAN,
        metadata={"description": "The type of user who last updated the work item status"},
    )
    """The type of user who last updated the work item status."""

    initial_messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "The initial conversation messages for this work item"},
    )
    """The original messages in the work item conversation."""

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

    callbacks: list[WorkItemCallback] = field(
        default_factory=list,
        metadata={"description": "The callbacks for the work item"},
    )
    """The callbacks for the work item."""

    def model_dump(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_by": self.completed_by.value if self.completed_by else None,
            "status_updated_at": self.status_updated_at.isoformat(),
            "status_updated_by": self.status_updated_by.value,
            "initial_messages": [msg.model_dump() for msg in self.initial_messages],
            "messages": [msg.model_dump() for msg in self.messages],
            "payload": self.payload,
            "callbacks": [callback.model_dump() for callback in self.callbacks],
        }

    def to_initiate_stream_payload(self) -> InitiateStreamPayload:
        return InitiateStreamPayload(
            agent_id=self.agent_id or "",
            thread_id=self.thread_id,
            name=f"Work Item {self.work_item_id}",
            messages=self.messages,
            metadata={
                "from_work_item": True,
                "work_item_id": self.work_item_id,
            },
        )

    @classmethod
    def model_validate(cls, data: dict) -> "WorkItem":  # noqa: C901, PLR0912
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
        if "completed_by" in data and isinstance(data["completed_by"], str):
            data["completed_by"] = WorkItemCompletedBy(data["completed_by"])
        if "status_updated_at" in data and isinstance(data["status_updated_at"], str):
            data["status_updated_at"] = datetime.fromisoformat(data["status_updated_at"])
        if "status_updated_by" in data and isinstance(data["status_updated_by"], str):
            data["status_updated_by"] = WorkItemStatusUpdatedBy(data["status_updated_by"])
        if "messages" in data:
            data["messages"] = [
                ThreadMessage.model_validate(msg) if isinstance(msg, dict) else msg
                for msg in data["messages"]
            ]
        if "callbacks" in data and data["callbacks"] is not None:
            data["callbacks"] = [
                WorkItemCallback.model_validate(callback)
                if isinstance(callback, dict)
                else callback
                for callback in data["callbacks"]
            ]
        if "initial_messages" in data and data["initial_messages"] is not None:
            data["initial_messages"] = [
                ThreadMessage.model_validate(msg) if isinstance(msg, dict) else msg
                for msg in data["initial_messages"]
            ]

        return cls(**data)

    def restart(self, user_id: str) -> None:
        """
        Restart the work item.

        This will reset the work item to the initial state,
        but keep the starting message(s).
        """
        self.status = WorkItemStatus.PENDING
        self.thread_id = None
        # Make sure the ThreadMessages get a new ID
        self.messages = [msg.copy_with_new_ids() for msg in self.initial_messages]
        self.updated_at = datetime.now(UTC)
        self.status_updated_at = datetime.now(UTC)
        self.status_updated_by = WorkItemStatusUpdatedBy.HUMAN
        self.completed_by = None
