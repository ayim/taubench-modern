import asyncio
import itertools
import math
from collections import defaultdict

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from agent_platform.workitems.config import Settings
from agent_platform.workitems.models import (
    WorkItemMessage,
    WorkItemMessageContent,
)
from agent_platform.workitems.models.workitem import WorkItemStatus
from agent_platform.workitems.orm.workitem import WorkItemORM
from agent_platform.workitems.worker import (
    execute_work_item,
    run_agent,
    run_batch,
    worker_iteration,
)


class TestWorker:
    """Test the execution of work items."""

    @pytest.mark.asyncio
    async def test_execute_work_item(self, require_docker, session: Session):
        item = WorkItemORM(
            agent_id="test-agent-1",
            thread_id="test-thread-1",
            status=WorkItemStatus.PENDING,
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Service test message")],
                ).model_dump()
            ],
            payload={},
        )
        session.add(item)
        session.commit()

        await execute_work_item(session, item, run_agent)

        result = session.execute(
            select(WorkItemORM).where(WorkItemORM.work_item_id == item.work_item_id)
        )
        actual: WorkItemORM | None = result.scalar_one_or_none()
        assert actual is not None, "Did not find work item"
        assert actual.status == WorkItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_errored_work_item(self, require_docker, session: Session):
        """Test that a work item is marked as errored when the agent
        function raises an exception."""

        async def error_run_agent(session: Session, item: WorkItemORM) -> bool:
            raise Exception("Test error")

        item = WorkItemORM(
            agent_id="test-agent-1",
            thread_id="test-thread-1",
            status=WorkItemStatus.PENDING,
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Service test message")],
                ).model_dump()
            ],
            payload={},
        )
        session.add(item)
        session.commit()

        await execute_work_item(session, item, error_run_agent)

        result = session.execute(
            select(WorkItemORM).where(WorkItemORM.work_item_id == item.work_item_id)
        )
        actual: WorkItemORM | None = result.scalar_one_or_none()
        assert actual is not None, "Did not find work item"
        assert actual.status == WorkItemStatus.ERROR

    @pytest.mark.asyncio
    async def test_failed_work_item(self, require_docker, session: Session):
        """Test that a work item is marked as failed when the agent function returns False."""

        async def fail_run_agent(session: Session, item: WorkItemORM) -> bool:
            return False

        item = WorkItemORM(
            agent_id="test-agent-1",
            thread_id="test-thread-1",
            status=WorkItemStatus.PENDING,
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Service test message")],
                ).model_dump()
            ],
            payload={},
        )
        session.add(item)
        session.commit()

        await execute_work_item(session, item, fail_run_agent)

        result = session.execute(
            select(WorkItemORM).where(WorkItemORM.work_item_id == item.work_item_id)
        )
        actual: WorkItemORM | None = result.scalar_one_or_none()
        assert actual is not None, "Did not find work item"
        assert actual.status == WorkItemStatus.ERROR

    @pytest.mark.asyncio
    async def test_batch_processing(self, require_docker, session: Session):
        """Test that a work item is marked as failed when the agent function returns False."""
        # fewer than the batch size, but larger than our sometimes_fail_run_agent()
        num_work_items = 5

        counter = itertools.count()

        async def sometimes_fail_run_agent(session: Session, item: WorkItemORM) -> bool:
            i = next(counter)  # Increment the counter
            match i % num_work_items:
                case 0:
                    # handled an error determined by execution of the agent
                    return False
                case 1:
                    # Unhandled failure during execution of the agent
                    raise Exception("injected error")
                case _:
                    return True

        # create a bunch of work items
        work_items = []
        for i in range(num_work_items):
            work_items.append(
                WorkItemORM(
                    agent_id=f"test-agent-{i}",
                    thread_id=f"test-thread-{i}",
                    status=WorkItemStatus.PENDING,
                    messages=[
                        WorkItemMessage(
                            role="user",
                            content=[
                                WorkItemMessageContent(kind="text", text="Service test message")
                            ],
                        ).model_dump()
                    ],
                    payload={},
                )
            )
        session.add_all(work_items)
        session.commit()

        # Override execute_work_item to call our `sometimes_fail_run_agent()` function
        async def custom_execute_work_item(session: Session, item: WorkItemORM) -> bool:
            """Custom execute work item that logs the work item id and status."""
            result = await execute_work_item(session, item, sometimes_fail_run_agent)
            return result

        # Run the batch
        work_item_ids = [wi.work_item_id for wi in work_items]
        results = await run_batch(
            session,
            work_item_ids,
            custom_execute_work_item,
            1200.0,  # 20 minutes timeout
        )

        # Verify the results from each work item
        assert len(results) == num_work_items
        assert sum(1 for r in results if isinstance(r, bool) and r is False) == 2  # handled failure
        assert sum(1 for r in results if isinstance(r, bool) and r is True) == 3  # success

        # Verify the statuses of those work items in the database
        results = session.execute(
            select(WorkItemORM.work_item_id, WorkItemORM.status).where(
                WorkItemORM.work_item_id.in_(work_item_ids)
            )
        )

        rows_by_status = defaultdict(list)
        for row in results.fetchall():
            rows_by_status[row.status].append(row.work_item_id)

        assert len(rows_by_status[WorkItemStatus.ERROR]) == 2, (
            f"Expected 2 workitems in error, got {rows_by_status[WorkItemStatus.ERROR]}"
        )
        assert len(rows_by_status[WorkItemStatus.COMPLETED]) == 3, (
            f"Expected 3 workitems in completed, got {rows_by_status[WorkItemStatus.COMPLETED]}"
        )

    @pytest.mark.asyncio
    async def test_worker_iteration(self, require_docker, session: Session):
        """Test multiple iterations pick up all work items."""
        # With a batch size of 5, we need to have 5 iterations to pick up all of the work
        num_work_items = 21
        max_batch_size = 5

        # create a bunch of work items
        work_items = []
        for i in range(num_work_items):
            work_items.append(
                WorkItemORM(
                    agent_id=f"test-agent-{i}",
                    thread_id=f"test-thread-{i}",
                    status=WorkItemStatus.PENDING,
                    messages=[
                        WorkItemMessage(
                            role="user",
                            content=[
                                WorkItemMessageContent(kind="text", text="Service test message")
                            ],
                        ).model_dump()
                    ],
                    payload={},
                )
            )
        session.add_all(work_items)
        session.commit()

        work_item_ids = [wi.work_item_id for wi in work_items]

        # Run a number of iterations
        config = Settings(max_batch_size=max_batch_size)
        for _ in range(math.ceil(num_work_items / max_batch_size)):
            await worker_iteration(
                session,
                config,
                run_agent,
            )

        # Verify the statuses of those work items in the database
        results = session.execute(
            select(WorkItemORM.work_item_id, WorkItemORM.status).where(
                WorkItemORM.work_item_id.in_(work_item_ids)
            )
        )
        rows = results.fetchall()
        assert len(rows) == num_work_items, f"Expected {num_work_items} workitems, got {len(rows)}"
        assert all(row.status == WorkItemStatus.COMPLETED for row in rows), (
            f"Expected all workitems to be completed, got {rows}"
        )

    @pytest.mark.asyncio
    async def test_timeout_work_item(self, require_docker, session: Session):
        """Test that a work item is marked as ERROR when timeout is exceeded,
        while other work items in the same batch can complete successfully."""

        call_count = 0

        async def slow_agent_func(session: Session, item: WorkItemORM) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call takes 5 seconds - longer than our 1 second timeout
                await asyncio.sleep(5)
            # Future calls return immediately
            return True

        # Create two work items
        item1 = WorkItemORM(
            agent_id="test-agent-timeout-1",
            thread_id="test-thread-timeout-1",
            status=WorkItemStatus.PENDING,
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Timeout test message 1")],
                ).model_dump()
            ],
            payload={},
        )
        item2 = WorkItemORM(
            agent_id="test-agent-timeout-2",
            thread_id="test-thread-timeout-2",
            status=WorkItemStatus.PENDING,
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Timeout test message 2")],
                ).model_dump()
            ],
            payload={},
        )
        session.add_all([item1, item2])
        session.commit()

        # Create config with 1 second timeout and batch size of 2 to process both items together
        config = Settings(work_item_timeout=1.0, max_batch_size=2)

        # Run worker iteration (first item should timeout, second should complete)
        await worker_iteration(session, config, slow_agent_func)

        # Verify the work item statuses
        result = session.execute(
            select(WorkItemORM.work_item_id, WorkItemORM.status).where(
                WorkItemORM.work_item_id.in_([item1.work_item_id, item2.work_item_id])
            )
        )
        statuses = {row.work_item_id: row.status for row in result.fetchall()}

        # Should have one ERROR and one COMPLETED
        status_counts: defaultdict[WorkItemStatus, int] = defaultdict(int)
        for status in statuses.values():
            status_counts[status] += 1

        assert status_counts[WorkItemStatus.ERROR] == 1, (
            f"Expected 1 ERROR work item, got {status_counts[WorkItemStatus.ERROR]}"
        )
        assert status_counts[WorkItemStatus.COMPLETED] == 1, (
            f"Expected 1 COMPLETED work item, got {status_counts[WorkItemStatus.COMPLETED]}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_worker_iterations(self, require_docker, database_url: str):
        """Test that concurrent worker iterations process work items without conflicts."""
        engine = create_engine(database_url, echo=True)
        factory = sessionmaker(bind=engine)

        # Track work_item_ids that have been processed
        processed_work_item_ids: set[str] = set()
        processing_lock = asyncio.Lock()

        async def tracking_agent_func(session: Session, item: WorkItemORM) -> bool:
            """Custom agent function that tracks which work_item_ids have been processed."""
            async with processing_lock:
                processed_work_item_ids.add(item.work_item_id)
            # Small delay to simulate work
            await asyncio.sleep(0.1)
            return True

        with factory() as session:
            # Create 10 work items
            work_items = []
            for i in range(10):
                work_items.append(
                    WorkItemORM(
                        agent_id=f"test-agent-concurrent-{i}",
                        thread_id=f"test-thread-concurrent-{i}",
                        status=WorkItemStatus.PENDING,
                        messages=[
                            WorkItemMessage(
                                role="user",
                                content=[
                                    WorkItemMessageContent(kind="text", text=f"test message {i}")
                                ],
                            ).model_dump()
                        ],
                        payload={},
                    )
                )
            session.add_all(work_items)
            session.commit()

            # Create set of expected work_item_ids
            expected_work_item_ids = {wi.work_item_id for wi in work_items}

        # Create config with batch size of 5
        config = Settings(max_batch_size=5)

        with factory() as session1, factory() as session2:
            # Start two concurrent worker iterations. Give them their own Session to simulate
            # separate processes.
            await asyncio.gather(
                worker_iteration(session1, config, tracking_agent_func),
                worker_iteration(session2, config, tracking_agent_func),
            )

        with factory() as session:
            # Verify all work items are COMPLETED
            result = session.execute(
                select(WorkItemORM.work_item_id, WorkItemORM.status).where(
                    WorkItemORM.work_item_id.in_(expected_work_item_ids)
                )
            )
            statuses = {row.work_item_id: row.status for row in result.fetchall()}

        # All work items should be completed
        completed_count = sum(
            1 for status in statuses.values() if status == WorkItemStatus.COMPLETED
        )
        assert completed_count == 10, f"Expected 10 COMPLETED work items, got {completed_count}"

        # Verify that processed work_item_ids exactly match expected work_item_ids
        assert processed_work_item_ids == expected_work_item_ids, (
            f"Processed work items {processed_work_item_ids} don't "
            "match expected {expected_work_item_ids}"
        )

        engine.dispose()
