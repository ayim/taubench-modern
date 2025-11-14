import asyncio
import math
from collections import defaultdict
from uuid import uuid4

import pytest

from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadUserMessage
from agent_platform.core.work_items import WorkItem, WorkItemCompletedBy, WorkItemStatus
from agent_platform.server.storage.option import StorageService
from agent_platform.server.work_items.batch_executor import BatchExecutor
from agent_platform.server.work_items.settings import Settings as WorkerSettings

pytest_plugins = ("server.tests.endpoints.conftest",)


@pytest.fixture(autouse=True)
def stub_validate_work_item_result(mocker):
    return mocker.patch(
        "agent_platform.server.work_items.judge._validate_success",
        return_value=WorkItemStatus.COMPLETED,
    )


def _make_work_item(
    owner_user_id: str,
    created_by_user_id: str,
    agent_id: str,
    text: str = "test message",
) -> WorkItem:
    """Convenience helper to build a PENDING WorkItem for the given user/agent."""
    return WorkItem(
        work_item_id=str(uuid4()),
        user_id=owner_user_id,
        created_by=created_by_user_id,
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
    # Patch settings where they are imported
    monkeypatch.setattr(
        "agent_platform.server.work_items.settings.WORK_ITEMS_SETTINGS", test_settings
    )

    # Mock the quotas service's get_max_parallel_work_items_in_process to return 5
    async def mock_get_instance():
        from unittest.mock import Mock

        mock_quotas = Mock()
        mock_quotas.get_max_parallel_work_items_in_process.return_value = 5
        return mock_quotas

    monkeypatch.setattr(
        "agent_platform.core.configurations.quotas.QuotasService.get_instance",
        mock_get_instance,
    )

    return test_settings


@pytest.fixture
def batch_executor(configured_storage, system_user) -> BatchExecutor:
    """Create a BatchExecutor that always returns success."""

    # Mock a work function that always returns success and records that status.
    async def work_func(item: WorkItem) -> bool:
        from agent_platform.core.work_items import WorkItemCompletedBy

        # Mark the work item as completed
        await configured_storage.complete_work_item(
            system_user.user_id, item.work_item_id, WorkItemCompletedBy.AGENT
        )
        return True

    return BatchExecutor(execute_work_item=work_func)


@pytest.fixture
async def system_user(storage):
    user, created = await storage.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    assert created is False, "User should already exist"
    return user


# ---------------------------------------------------------------------------
# Tests for BatchExecutor
# ---------------------------------------------------------------------------


class TestBatchExecutor:
    """Tests specifically for the BatchExecutor functionality.

    These tests focus on the batch execution mode, including worker iterations,
    timeouts, and concurrent execution handling.
    """

    # --------------------------------------------------
    # worker_iteration multiple passes
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_worker_iteration(
        self,
        configured_storage,
        stub_user,
        system_user,
        seed_agents,
        batch_executor,
    ):
        num_work_items = 21
        max_batch_size = 5  # From fixture

        # Add work-items
        for _ in range(num_work_items):
            await configured_storage.create_work_item(
                _make_work_item(system_user.user_id, stub_user.user_id, seed_agents[0].agent_id)
            )

        # Run enough iterations to pick them all up
        iterations = math.ceil(num_work_items / max_batch_size)
        for _ in range(iterations):
            await batch_executor._worker_iteration()

        # All should be COMPLETED
        items = await configured_storage.list_work_items()
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
        system_user,
        seed_agents,
        batch_executor,
    ):
        call_count = 0

        async def slow_agent(wi: WorkItem) -> bool:
            """
            The first work item takes a very long time to complete, others complete quickly.
            """
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(5)  # exceeds timeout

            # Mark the work item as completed
            await configured_storage.complete_work_item(
                system_user.user_id, wi.work_item_id, WorkItemCompletedBy.AGENT
            )
            return True

        batch_executor.execute_work_item = slow_agent

        # Two work-items: first will timeout, second succeeds
        items = [
            _make_work_item(
                stub_user.user_id, stub_user.user_id, seed_agents[0].agent_id, "timeout-1"
            ),
            _make_work_item(
                stub_user.user_id, stub_user.user_id, seed_agents[0].agent_id, "timeout-2"
            ),
        ]
        for wi in items:
            await configured_storage.create_work_item(wi)

        await batch_executor._worker_iteration()

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
        system_user,
        seed_agents,
        batch_executor,
    ):
        # Track the work-items we executed as a list and *not* as a set.
        # We don't want the set to mask us running the same work-item multiple times.
        processed_ids = []
        lock = asyncio.Lock()

        # Add tracking on top of the original complete-normally mock.
        orig_func = batch_executor.execute_work_item

        async def tracking_agent(wi: WorkItem) -> bool:
            async with lock:
                processed_ids.append(wi.work_item_id)
            await asyncio.sleep(0.05)
            return await orig_func(wi)

        batch_executor.execute_work_item = tracking_agent

        # Create 10 work-items
        work_items = [
            _make_work_item(
                stub_user.user_id, stub_user.user_id, seed_agents[0].agent_id, f"msg-{i}"
            )
            for i in range(10)
        ]
        for wi in work_items:
            await configured_storage.create_work_item(wi)

        expected_ids = [wi.work_item_id for wi in work_items]

        # Set the custom work function on the service
        batch_executor.execute_work_item = tracking_agent

        await asyncio.gather(
            batch_executor._worker_iteration(),
            batch_executor._worker_iteration(),
        )

        # Post-conditions
        items = await configured_storage.get_work_items_by_ids(list(expected_ids))
        assert all(item.status == WorkItemStatus.COMPLETED for item in items)
        assert processed_ids.sort() == expected_ids.sort()
