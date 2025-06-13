from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import (
    CreateWorkItemPayload,
    WorkItem,
    WorkItemORM,
    WorkItemStatus,
    orm_to_model,
)


async def create_work_item(session: Session, payload: CreateWorkItemPayload) -> WorkItem:
    work_item = WorkItemORM(
        agent_id=payload.agent_id,
        thread_id=payload.thread_id,
        messages=[
            msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in payload.messages
        ],
        payload=payload.payload,
    )
    session.add(work_item)
    session.commit()
    session.refresh(work_item)
    return orm_to_model(work_item)


async def get_work_item(session: Session, work_item_id: str) -> WorkItem | None:
    result = session.execute(select(WorkItemORM).where(WorkItemORM.work_item_id == work_item_id))
    orm_item = result.scalar_one_or_none()
    return orm_to_model(orm_item) if orm_item else None


async def list_work_items(session: Session, limit: int = 100) -> list[WorkItem]:
    result = session.execute(select(WorkItemORM).limit(limit))
    return [orm_to_model(item) for item in result.scalars().all()]


async def update_status(
    session: Session,
    work_item_id: str,
    status: WorkItemStatus,
    status_updated_by: str,
) -> WorkItem | None:
    session.execute(
        update(WorkItemORM)
        .where(WorkItemORM.work_item_id == work_item_id)
        .values(status=status, status_updated_by=status_updated_by)
    )
    session.commit()
    return await get_work_item(session, work_item_id)


async def cancel_work_item(session: Session, work_item_id: str) -> None:
    session.execute(delete(WorkItemORM).where(WorkItemORM.work_item_id == work_item_id))
    session.commit()
