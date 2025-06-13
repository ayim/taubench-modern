from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import uuid4

from sqlalchemy import JSON, TIMESTAMP, Enum, String, text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


class WorkItemStatus(StrEnum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"


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
    messages: list[Any] = field(default_factory=list)
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
            "messages": [
                msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in self.messages
            ],
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


@dataclass
class CreateWorkItemPayload:
    """Payload to create a work item."""

    agent_id: str
    thread_id: str
    messages: list[Any] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


class WorkItemORM(Base):
    __tablename__ = "work_items"

    work_item_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(WorkItemStatus), nullable=False, default=WorkItemStatus.PENDING
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


def orm_to_model(orm: WorkItemORM) -> WorkItem:
    """Convert a WorkItemORM to its API representation."""
    return WorkItem(
        work_item_id=orm.work_item_id,
        agent_id=orm.agent_id,
        thread_id=orm.thread_id,
        status=orm.status,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        completed_by=orm.completed_by,
        status_updated_at=orm.status_updated_at,
        status_updated_by=orm.status_updated_by,
        messages=[msg for msg in orm.messages],
        payload=orm.payload,
    )


def model_to_orm(model: WorkItem) -> WorkItemORM:
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
        messages=[
            msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in model.messages
        ],
        payload=model.payload,
    )
