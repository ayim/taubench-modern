import asyncio
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import settings
from .db import DatabaseManager
from .models import WorkItemORM, WorkItemStatus

logger = logging.getLogger(__name__)


async def process_pending_item(session: Session, item: WorkItemORM) -> None:
    session.execute(
        update(WorkItemORM)
        .where(WorkItemORM.work_item_id == item.work_item_id)
        .values(status=WorkItemStatus.EXECUTING)
    )
    session.commit()

    # TODO: invoke agent server
    await asyncio.sleep(0)

    session.execute(
        update(WorkItemORM)
        .where(WorkItemORM.work_item_id == item.work_item_id)
        .values(status=WorkItemStatus.COMPLETED)
    )
    session.commit()


async def worker_loop(db: DatabaseManager, shutdown_event: asyncio.Event) -> None:
    while not shutdown_event.is_set():
        with db.session() as session:
            result = session.execute(
                select(WorkItemORM)
                .where(WorkItemORM.status == WorkItemStatus.PENDING.value)
                .with_for_update(skip_locked=True)
                .limit(5)
            )
            items = result.scalars().all()
            for item in items:
                await process_pending_item(session, item)

        await asyncio.sleep(settings.worker_interval)

    logger.info("finished work-items worker loop")
