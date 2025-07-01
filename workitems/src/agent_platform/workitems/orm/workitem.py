from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, TIMESTAMP, String, text
from sqlalchemy.orm import Mapped, mapped_column

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload

from ..models import WorkItem, WorkItemMessage, WorkItemStatus
from .base import Base


class WorkItemORM(Base):
    __tablename__ = "work_items"

    work_item_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=WorkItemStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
    completed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    status_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    status_updated_by: Mapped[str] = mapped_column(String, nullable=False, default="SYSTEM")
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    def to_model(self) -> WorkItem:
        """Convert a WorkItemORM to its API representation."""
        return WorkItem(
            work_item_id=self.work_item_id,
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_by=self.completed_by,
            status_updated_at=self.status_updated_at,
            status_updated_by=self.status_updated_by,
            messages=[WorkItemMessage.model_validate(msg) for msg in self.messages],
            payload=self.payload,
        )

    def to_invoke_payload(self) -> InitiateStreamPayload:
        """Convert a WorkItemORM to an InvokeAgentPayload."""
        work_item_messages = [WorkItemMessage.model_validate(msg) for msg in self.messages]
        thread_messages = [msg.to_thread_message() for msg in work_item_messages]

        return InitiateStreamPayload(
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            messages=thread_messages,
        )

    @classmethod
    def from_model(cls, model: WorkItem) -> "WorkItemORM":
        """Create a WorkItemORM from an API model."""
        return WorkItemORM(
            work_item_id=model.work_item_id,
            agent_id=model.agent_id,
            thread_id=model.thread_id,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_by=model.completed_by,
            status_updated_at=model.status_updated_at,
            status_updated_by=model.status_updated_by,
            messages=[msg.model_dump() for msg in model.messages],
            payload=model.payload,
        )
