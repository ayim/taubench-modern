import asyncio
import itertools
import math
from collections import defaultdict
from uuid import uuid4

import pytest

from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadUserMessage
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage.option import StorageService
from agent_platform.server.work_items import background_worker as bw
from agent_platform.server.work_items.settings import Settings as WorkerSettings

pytest_plugins = ("server.tests.endpoints.conftest",)

# ---------------------------------------------------------------------------
# Helper: create a minimal WorkItem in the PENDING state
# ---------------------------------------------------------------------------


def _make_work_item(user_id: str, agent_id: str, text: str = "test message") -> WorkItem:
    """Convenience helper to build a PENDING WorkItem for the given user/agent."""
    return WorkItem(
        work_item_id=str(uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
        messages=[ThreadUserMessage(content=[ThreadTextContent(text=text)])],
        payload={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def configured_storage(storage):
    """Point the StorageService singleton used by background_worker at the test DB."""
    StorageService.reset()
    StorageService.set_for_testing(storage)
    return storage


@pytest.fixture(autouse=True)
def patch_worker_settings(monkeypatch):
    """Shrink worker settings so tests run quickly (small sleeps, small batches)."""
    test_settings = WorkerSettings(worker_interval=0, max_batch_size=5, work_item_timeout=1.0)
    monkeypatch.setattr(bw, "WORK_ITEMS_SETTINGS", test_settings, raising=False)
    return test_settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackgroundWorker:
    """Port of the legacy work-items worker tests to the new background_worker."""

    # --------------------------------------------------
    # execute_work_item
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_execute_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def mock_agent_func(wi: WorkItem) -> bool:
            return True

        result = await bw.execute_work_item(item, mock_agent_func)
        assert result is True

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.COMPLETED

    # --------------------------------------------------
    # errored_work_item (agent raises)
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_errored_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def error_agent_func(_: WorkItem) -> bool:
            raise Exception("Test error")

        result = await bw.execute_work_item(item, error_agent_func)
        assert result is False

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.ERROR

    # --------------------------------------------------
    # failed_work_item (agent returns False)
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_failed_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def fail_agent_func(_: WorkItem) -> bool:
            return False

        result = await bw.execute_work_item(item, fail_agent_func)
        assert result is False

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.ERROR

    # --------------------------------------------------
    # batch_processing
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_batch_processing(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        num_work_items = 5
        counter = itertools.count()

        async def sometimes_fail_agent(_: WorkItem) -> bool:
            i = next(counter)
            match i % num_work_items:
                case 0:
                    return False  # handled failure
                case 1:
                    raise Exception("Injected error")  # unhandled --> becomes ERROR
                case _:
                    return True

        # Seed work-items in DB
        work_items: list[WorkItem] = []
        for _ in range(num_work_items):
            wi = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
            work_items.append(wi)
            await configured_storage.create_work_item(wi)

        work_item_ids = [wi.work_item_id for wi in work_items]
        results = await bw.run_batch(work_item_ids, sometimes_fail_agent, batch_timeout=2.0)

        # Expectations: 3 successes, 2 handled failures (False)
        assert len(results) == num_work_items
        assert sum(1 for r in results if r is True) == 3
        assert sum(1 for r in results if r is False) == 2

        # Verify DB statuses
        items = await configured_storage.get_work_items_by_ids(work_item_ids)
        rows_by_status: defaultdict[WorkItemStatus, list[str]] = defaultdict(list)
        for item in items:
            rows_by_status[item.status].append(item.work_item_id)

        assert len(rows_by_status[WorkItemStatus.ERROR]) == 2
        assert len(rows_by_status[WorkItemStatus.COMPLETED]) == 3

    # --------------------------------------------------
    # worker_iteration multiple passes
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_worker_iteration(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        num_work_items = 21
        max_batch_size = bw.WORK_ITEMS_SETTINGS.max_batch_size  # 5 in fixture

        async def always_succeed(_: WorkItem) -> bool:
            return True

        # Add work-items
        for _ in range(num_work_items):
            await configured_storage.create_work_item(
                _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
            )

        # Run enough iterations to pick them all up
        iterations = math.ceil(num_work_items / max_batch_size)
        for _ in range(iterations):
            await bw.worker_iteration(always_succeed)

        # All should be COMPLETED
        items = await configured_storage.list_work_items(stub_user.user_id)
        assert len(items) == num_work_items
        assert all(item.status == WorkItemStatus.COMPLETED for item in items)

    # --------------------------------------------------
    # timeout_work_item
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_timeout_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        call_count = 0

        async def slow_agent(wi: WorkItem) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(5)  # exceeds timeout
            return True

        # Two work-items: first will timeout, second succeeds
        items = [
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, "timeout-1"),
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, "timeout-2"),
        ]
        for wi in items:
            await configured_storage.create_work_item(wi)

        await bw.worker_iteration(slow_agent)

        statuses = {
            wi.work_item_id: (await configured_storage.get_work_item(wi.work_item_id)).status
            for wi in items
        }
        status_counts: defaultdict[WorkItemStatus, int] = defaultdict(int)
        for st in statuses.values():
            status_counts[st] += 1

        assert status_counts[WorkItemStatus.ERROR] == 1
        assert status_counts[WorkItemStatus.COMPLETED] == 1

    # --------------------------------------------------
    # concurrent_worker_iterations
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_concurrent_worker_iterations(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        processed_ids: set[str] = set()
        lock = asyncio.Lock()

        async def tracking_agent(wi: WorkItem) -> bool:
            async with lock:
                processed_ids.add(wi.work_item_id)
            await asyncio.sleep(0.05)
            return True

        # Create 10 work-items
        work_items = [
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, f"msg-{i}")
            for i in range(10)
        ]
        for wi in work_items:
            await configured_storage.create_work_item(wi)

        expected_ids = {wi.work_item_id for wi in work_items}

        await asyncio.gather(
            bw.worker_iteration(tracking_agent),
            bw.worker_iteration(tracking_agent),
        )

        # Post-conditions
        items = await configured_storage.get_work_items_by_ids(list(expected_ids))
        assert all(item.status == WorkItemStatus.COMPLETED for item in items)
        assert processed_ids == expected_ids
