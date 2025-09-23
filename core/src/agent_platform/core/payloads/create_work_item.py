from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCallback,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)


@dataclass
class CreateWorkItemPayload:
    """Payload for creating a work item."""

    agent_id: str = field(
        metadata={"description": "The ID of the agent that will process this work item."},
    )
    """The ID of the agent that will process this work item."""

    messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "The messages in the work item conversation."},
    )
    """The messages in the work item conversation."""

    payload: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The payload of the work item."},
    )
    """The payload of the work item."""

    work_item_id: str | None = field(
        default=None,
        metadata={"description": "The ID of the work item."},
    )
    """The ID of the work item."""

    work_item_name: str | None = field(
        default=None,
        metadata={
            "description": "User-friendly name for the work item.Must be less than 255 characters."
        },
    )
    """User-friendly name for the work item. Must be less than 255 characters."""

    callbacks: list[WorkItemCallback] | None = field(
        default=None,
        metadata={
            "description": "A list of callbacks to trigger when the"
            " work item reaches a certain status."
        },
    )
    """A list of callbacks to trigger when the work item reaches a certain status."""

    @classmethod
    def to_work_item(
        cls,
        payload: "CreateWorkItemPayload",
        owner_user_id: str,
        created_by_user_id: str,
    ) -> WorkItem:
        return WorkItem(
            user_id=owner_user_id,
            created_by=created_by_user_id,
            agent_id=payload.agent_id,
            thread_id=None,
            initial_messages=payload.messages,
            messages=payload.messages,
            payload=payload.payload,
            work_item_id=str(uuid4()),
            work_item_name=WorkItem.normalize_work_item_name(payload.work_item_name),
            status=WorkItemStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            completed_by=None,  # Not completed yet
            status_updated_at=datetime.now(UTC),
            status_updated_by=WorkItemStatusUpdatedBy.HUMAN,
            callbacks=payload.callbacks or [],
        )
