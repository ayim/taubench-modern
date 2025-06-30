import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.workitems.config import Settings
from agent_platform.workitems.db import DatabaseManager
from agent_platform.workitems.models import WorkItemStatus
from agent_platform.workitems.orm import WorkItemORM

logger = logging.getLogger(__name__)


async def run_agent(session: AsyncSession, item: WorkItemORM) -> bool:
    """
    Run an agent on the agent_server.
    """
    # TODO: actually invoke agent server
    await asyncio.sleep(0.5)
    return True


async def worker_loop(
    db: DatabaseManager,
    config: Settings,
    shutdown_event: asyncio.Event,
    work_func: Callable[[AsyncSession, WorkItemORM], Awaitable[bool]],
) -> None:
    """
    Runs a loop which processes work items, sleeping the configured amount between iterations.
    """
    while not shutdown_event.is_set():
        logger.info("searching for work items to process")
        try:
            await worker_iteration(db, config, work_func)
        except Exception as exc:
            logger.error(f"Error processing work items: {exc}", exc_info=exc)

        await asyncio.sleep(config.worker_interval)

    logger.info("finished work-items worker loop")


async def worker_iteration(
    db: DatabaseManager,
    config: Settings,
    work_func: Callable[[AsyncSession, WorkItemORM], Awaitable[bool]],
) -> None:
    """
    Reads a batch of "PENDING" work_item rows from the database and
    marks them as "EXECUTING" and processes them as a batch.
    """
    # 1) candidate CTE: find the next 10 pending work items
    async with db.session() as session:
        candidate = (
            select(WorkItemORM.work_item_id)
            .where(WorkItemORM.status == WorkItemStatus.PENDING.value)
            .with_for_update(skip_locked=True)
            .limit(config.max_batch_size)
            .cte("candidate")
        )
        async with session.begin():
            results = await session.execute(
                update(WorkItemORM)
                .values(status=WorkItemStatus.EXECUTING.value, updated_at=func.now())
                .where(WorkItemORM.work_item_id == candidate.c.work_item_id)
                .returning(WorkItemORM.work_item_id)
            )
            # collect all rows, using asyncio.gather
            work_item_ids = results.scalars().fetchall()

    logger.info(f"Found {len(work_item_ids)} work items to process. {work_item_ids!r}")

    if work_item_ids:
        logger.info(f"Dispatching work items {work_item_ids}")
        batch_results = await run_batch(db, work_item_ids, work_func, config.work_item_timeout)
        logger.info(f"Completed {len(batch_results)} work items concurrently")


async def run_batch(
    db: DatabaseManager,
    work_item_ids: Sequence[str],
    work_func: Callable[[AsyncSession, WorkItemORM], Awaitable[bool]],
    batch_timeout: float,
) -> Sequence[bool | BaseException]:
    """
    Given a list of work_item_ids, fetch the full work_item objects, and
    execute a task to run each. Wait for completion over all tasks.
    """
    # Get all work items in a single query
    async with db.begin() as session:
        stmt = select(WorkItemORM).where(WorkItemORM.work_item_id.in_(work_item_ids))
        items = (await session.execute(stmt)).scalars().all()

    # Failed to find any work_items in the database to operate on.
    if not items:
        return []

    # Create tasks for each work item
    tasks = {}
    for item in items:
        logger.info(f"Dispatching work item (batch run) {item.work_item_id}")
        task = asyncio.create_task(execute_work_item(db, item, work_func))
        tasks[item.work_item_id] = task

    # Run all tasks concurrently until they are all completed or a timeout is reached.
    results: list[bool | BaseException] = []
    incomplete_work_item_ids = []

    done, pending = await asyncio.wait(
        tasks.values(), timeout=batch_timeout, return_when=asyncio.ALL_COMPLETED
    )

    # Collect the pending tasks.
    if pending:
        # Some tasks didn't complete within timeout
        logger.warning(
            f"Batch timeout ({batch_timeout}s) exceeded for "
            f"{len(pending)} of {len(tasks)} work items"
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

    for task, item in zip(tasks.values(), items, strict=True):
        if task in done:
            # Task completed before timeout - get its result
            try:
                results.append(task.result())
                logger.info(f"Work item {item.work_item_id} completed normally")
            except Exception as e:
                results.append(e)
                logger.warning(f"Work item {item.work_item_id} failed with error: {e}", exc_info=e)
        else:
            # Task didn't complete - mark as ERROR
            incomplete_work_item_ids.append(item.work_item_id)
            results.append(TimeoutError("Work item timeout exceeded"))
            logger.error(f"Work item {item.work_item_id} timed out, marking as ERROR")

    # For all timed out work items which are still PENDING/EXECUTING, mark them as having ERROR'ed.
    # We do this to prevent races between the task writing to the DB after we signaled
    # the cancellation
    if incomplete_work_item_ids:
        async with session.begin():
            await session.execute(
                update(WorkItemORM)
                .where(
                    WorkItemORM.status.in_(
                        [WorkItemStatus.PENDING.value, WorkItemStatus.EXECUTING.value]
                    ),
                    WorkItemORM.work_item_id.in_(incomplete_work_item_ids),
                )
                .values(status=WorkItemStatus.ERROR)
            )

    return results


async def execute_work_item(
    db: DatabaseManager,
    item: WorkItemORM,
    agent_func: Callable[[AsyncSession, WorkItemORM], Awaitable[bool]],
) -> bool:
    logger.info(f"Starting execution on work item {item.work_item_id}")
    result = False

    try:
        async with db.session() as session:
            result = await agent_func(session, item)
    except Exception as e:
        logger.error(f"Error executing work item {item.work_item_id}: {e}", exc_info=e)

    new_status = WorkItemStatus.COMPLETED if result else WorkItemStatus.ERROR

    logger.info(f"Completed execution on work item {item.work_item_id}, result: {result}")

    async with db.begin() as session:
        await session.execute(
            update(WorkItemORM)
            .where(WorkItemORM.work_item_id == item.work_item_id)
            .values(status=new_status)
        )

    return result
