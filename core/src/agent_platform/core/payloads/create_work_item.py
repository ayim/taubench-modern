from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.work_items import WorkItem, WorkItemStatus


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

    @classmethod
    def to_work_item(cls, payload: "CreateWorkItemPayload", user_id: str) -> WorkItem:
        return WorkItem(
            user_id=user_id,
            agent_id=payload.agent_id,
            thread_id=None,
            messages=payload.messages,
            payload=payload.payload,
            work_item_id=str(uuid4()),
            status=WorkItemStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            completed_by=None,  # Not completed yet
            status_updated_at=datetime.now(UTC),
            status_updated_by=user_id,
        )
