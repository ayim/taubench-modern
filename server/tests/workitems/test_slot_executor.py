import asyncio
from collections import defaultdict
from unittest.mock import AsyncMock, Mock, call
from uuid import uuid4

import pytest

from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadUserMessage
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.work_items.slot_executor import SlotExecutor, SlotManager, SlotState

# ============================================================================
# Test Helpers
# ============================================================================


def make_work_item(
    work_item_id: str | None = None, agent_id: str | None = None, user_id: str | None = None
) -> WorkItem:
    """Create a test work item with minimal required fields."""
    return WorkItem(
        work_item_id=work_item_id or str(uuid4()),
        user_id=user_id or "test-user",
        created_by=user_id or "test-user",
        agent_id=agent_id or "test-agent",
        thread_id=None,
        status=WorkItemStatus.PENDING,
        messages=[ThreadUserMessage(content=[ThreadTextContent(text="test message")])],
        payload={},
    )


def make_mock_service():
    """Create a mock WorkItemsService with the essential methods."""
    service = Mock()
    service.execute_work_item = AsyncMock(return_value=True)
    service._work_func = AsyncMock(return_value=True)
    return service


def make_mock_storage():
    """Create a mock StorageService."""
    storage = Mock()
    storage.get_pending_work_item_ids = AsyncMock(return_value=[])
    storage.get_work_items_by_ids = AsyncMock(return_value=[])
    storage.mark_incomplete_work_items_as_error = AsyncMock()
    return storage


def make_mock_quotas(num_slots: int = 3):
    """Create a mock QuotasService."""
    quotas = Mock()
    quotas.get_max_parallel_work_items_in_process = Mock(return_value=num_slots)
    return quotas


class TestSlotManager:
    """Tests for SlotManager state tracking."""

    def test_get_num_free_slots_all_idle(self):
        """All slots idle returns correct count."""
        manager = SlotManager()
        manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
            2: SlotState(slot_id=2, status="idle"),
        }
        assert manager.get_num_free_slots() == 3

    def test_get_num_free_slots_all_executing(self):
        """All slots executing returns zero."""
        manager = SlotManager()
        manager.slots = {
            0: SlotState(slot_id=0, status="executing", work_item_id="item-1"),
            1: SlotState(slot_id=1, status="executing", work_item_id="item-2"),
            2: SlotState(slot_id=2, status="executing", work_item_id="item-3"),
        }
        assert manager.get_num_free_slots() == 0

    def test_get_num_free_slots_mixed(self):
        """Mixed idle/executing slots returns correct count."""
        manager = SlotManager()
        manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="executing", work_item_id="item-2"),
            2: SlotState(slot_id=2, status="idle"),
        }
        assert manager.get_num_free_slots() == 2

    def test_get_slot_status(self):
        """Returns correct status for all slots."""
        manager = SlotManager()
        manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="executing", work_item_id="item-2"),
        }
        status = manager.get_slot_status()
        assert len(status) == 2
        assert status[0] == {"slot_id": 0, "status": "idle", "work_item_id": None}
        assert status[1] == {"slot_id": 1, "status": "executing", "work_item_id": "item-2"}


class TestSlotExecutorInit:
    """Tests for SlotExecutor initialization."""

    def test_init_with_service(self):
        """Initializes with service and creates slot manager."""
        execute_work_item = AsyncMock(return_value=True)
        executor = SlotExecutor(execute_work_item)
        assert executor.execute_work_item is execute_work_item
        assert executor.slot_manager is not None
        assert len(executor.slot_manager.slots) == 0
        assert executor.get_slot_status() == []

    async def test_run_initializes_slots(self):
        """Run initializes the correct number of slots."""
        service = make_mock_service()
        quotas = make_mock_quotas(num_slots=3)
        storage = make_mock_storage()
        executor = SlotExecutor(service.execute_work_item, quotas=quotas, storage=storage)

        # Create a shutdown task that completes immediately
        shutdown_event = asyncio.Event()
        shutdown_event.set()
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        await executor.run(shutdown_task)

        # Verify slots were initialized
        assert len(executor.slot_manager.slots) == 3
        for i in range(3):
            assert i in executor.slot_manager.slots
            assert executor.slot_manager.slots[i].slot_id == i
            assert executor.slot_manager.slots[i].status == "idle"


class TestFetchAndQueueWorkItems:
    """Tests for the _fetch_and_queue_work_items method."""

    async def test_fetches_and_queues_items_when_slots_available(self):
        """Fetches work items and adds them to queue."""
        service = make_mock_service()
        storage = make_mock_storage()

        work_item_ids = ["item-1", "item-2"]
        work_items = [make_work_item(wid) for wid in work_item_ids]
        storage.get_pending_work_item_ids.return_value = work_item_ids
        storage.get_work_items_by_ids.return_value = work_items

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
        }

        await executor._fetch_and_queue_work_items()

        # Verify fetched correct number
        storage.get_pending_work_item_ids.assert_called_once_with(2)
        storage.get_work_items_by_ids.assert_called_once_with(work_item_ids)

        # Verify items were queued
        assert executor._work_queue.qsize() == 2
        item1 = await executor._work_queue.get()
        item2 = await executor._work_queue.get()
        assert item1.work_item_id in work_item_ids
        assert item2.work_item_id in work_item_ids

    async def test_respects_queue_size(self):
        """Only fetches items to fill gaps (free slots - queue size)."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
            2: SlotState(slot_id=2, status="idle"),
        }

        # Mock some data
        work_item_ids = ["item-2", "item-3"]
        work_items = [make_work_item(wid) for wid in work_item_ids]
        storage.get_pending_work_item_ids.return_value = work_item_ids
        storage.get_work_items_by_ids.return_value = work_items

        # Pre-populate with 1 item
        await executor._work_queue.put(make_work_item("item-1"))

        await executor._fetch_and_queue_work_items()

        storage.get_pending_work_item_ids.assert_called_once_with(2)
        storage.get_work_items_by_ids.assert_called_once_with(work_item_ids)

        assert executor._work_queue.qsize() == 3, (
            f"Expected 3 items in queue, got {executor._work_queue.qsize()}"
        )

    async def test_skips_fetch_when_no_slots_free(self):
        """Does not fetch when all slots are busy."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="executing", work_item_id="busy-1"),
            1: SlotState(slot_id=1, status="executing", work_item_id="busy-2"),
        }

        await executor._fetch_and_queue_work_items()

        # Should not call storage at all
        storage.get_pending_work_item_ids.assert_not_called()

    async def test_handles_empty_result(self):
        """Handles when storage returns no pending items."""
        service = make_mock_service()
        storage = make_mock_storage()
        storage.get_pending_work_item_ids.return_value = []

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
        }

        await executor._fetch_and_queue_work_items()

        # Verify no items queued
        assert executor._work_queue.empty()
        storage.get_work_items_by_ids.assert_not_called()


class TestReturnQueueToPool:
    """Tests for _return_queue_to_pool method."""

    async def test_returns_queue_to_pool(self):
        """Returns the queue to the pool."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Create some fake work items
        work_item_ids = ["test-work-item-1", "test-work-item-2"]
        storage.get_pending_work_item_ids.return_value = work_item_ids
        work_items = [make_work_item(wid) for wid in work_item_ids]
        storage.get_work_items_by_ids.return_value = work_items

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
        }
        await executor._fetch_and_queue_work_items()

        assert executor._work_queue.qsize() == 2

        storage.return_work_item_to_pool = AsyncMock(return_value=True)

        await executor._return_queue_to_pool()

        assert executor._work_queue.empty()

        storage.return_work_item_to_pool.assert_has_calls(
            [
                call(work_item_ids[0]),
                call(work_item_ids[1]),
            ]
        )


class TestExecuteWorkItemInSlot:
    """Tests for _execute_work_item_in_slot method."""

    async def test_successful_execution(self):
        """Successfully executes a work item and updates slot state."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        await executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=1.0)

        # Verify execution was called
        service.execute_work_item.assert_called_once()
        call_args = service.execute_work_item.call_args
        assert call_args[0][0].work_item_id == "item-1"

        # Verify slot is back to idle after completion
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None
        assert slot_state.task is None

    async def test_marks_slot_executing_during_execution(self):
        """Slot state shows executing during work item execution."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Make execution take some time
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.1)
            return True

        service.execute_work_item = AsyncMock(side_effect=slow_execute)

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        # Start execution
        exec_task = asyncio.create_task(
            executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=1.0)
        )

        # Check state during execution
        await asyncio.sleep(0.01)
        assert slot_state.status == "executing"
        assert slot_state.work_item_id == "item-1"
        assert slot_state.task is not None

        # Wait for completion
        await exec_task

        # Back to idle after completion
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None

    async def test_handles_timeout(self):
        """Handles work item timeout and marks item as error."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Make execution take longer than timeout
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(2.0)
            return True

        service.execute_work_item = AsyncMock(side_effect=slow_execute)

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        await executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=0.1)

        # Verify error was marked
        storage.mark_incomplete_work_items_as_error.assert_called_once_with(["item-1"])

        # Verify slot cleaned up
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None
        assert slot_state.task is None

    async def test_handles_execution_error(self):
        """Handles execution errors gracefully."""
        service = make_mock_service()
        storage = make_mock_storage()

        service.execute_work_item = AsyncMock(side_effect=ValueError("Test error"))

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        await executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=1.0)

        # Verify slot recovered
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None
        assert slot_state.task is None

    async def test_cleanup_always_happens(self):
        """Slot state is always cleaned up even on error during timeout handling."""
        service = make_mock_service()
        storage = make_mock_storage()
        storage.mark_incomplete_work_items_as_error = AsyncMock(side_effect=Exception("DB error"))

        # Make execution timeout
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(2.0)
            return True

        service.execute_work_item = AsyncMock(side_effect=slow_execute)

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        # Even if marking error fails, slot should be cleaned up
        # The exception from mark_incomplete_work_items_as_error will propagate,
        # but the finally block ensures cleanup
        with pytest.raises(Exception, match="DB error"):
            await executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=0.1)

        # Verify cleanup happened despite the exception
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None
        assert slot_state.task is None


class TestSlotExecutorTask:
    """Tests for slot executor task loop orchestration."""

    async def test_processes_items_from_queue(self):
        """Task processes work items from the queue."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {0: SlotState(slot_id=0, status="idle")}

        await executor._work_queue.put(make_work_item("item-1"))
        await executor._work_queue.put(make_work_item("item-2"))
        shutdown_event = asyncio.Event()

        # Start task
        slot_task = asyncio.create_task(
            executor._slot_executor_task(0, shutdown_event, work_item_timeout=1.0)
        )

        # Wait for processing
        await asyncio.sleep(0.1)
        shutdown_event.set()
        await slot_task

        # Verify items were processed
        assert service.execute_work_item.call_count == 2

    async def test_waits_when_queue_empty(self):
        """Task waits when queue is empty without busy-looping."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {0: SlotState(slot_id=0, status="idle")}

        shutdown_event = asyncio.Event()

        slot_task = asyncio.create_task(
            executor._slot_executor_task(0, shutdown_event, work_item_timeout=1.0)
        )

        # Wait a bit
        await asyncio.sleep(0.1)

        # No execution should have happened
        service.execute_work_item.assert_not_called()

        shutdown_event.set()
        await slot_task

    async def test_stops_on_shutdown(self):
        """Task stops gracefully when shutdown event is set."""
        service = make_mock_service()
        storage = make_mock_storage()

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {0: SlotState(slot_id=0, status="idle")}

        shutdown_event = asyncio.Event()

        slot_task = asyncio.create_task(
            executor._slot_executor_task(0, shutdown_event, work_item_timeout=1.0)
        )

        # Trigger shutdown immediately
        shutdown_event.set()
        await slot_task

        # Should complete without hanging


class TestSlotExecutorIntegration:
    """Integration tests for the full slot execution flow."""

    async def test_full_execution_flow_single_item(self):
        """Complete flow: reader fetches item, slot executes it."""
        service = make_mock_service()
        storage = make_mock_storage()
        quotas = make_mock_quotas(num_slots=2)

        work_item = make_work_item("item-1")
        storage.get_pending_work_item_ids.return_value = ["item-1"]
        storage.get_work_items_by_ids.return_value = [work_item]

        executor = SlotExecutor(service.execute_work_item, storage=storage, quotas=quotas)

        # Initialize slots
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
        }

        # Create shutdown mechanism
        shutdown_event = asyncio.Event()
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Start executor in background
        executor_task = asyncio.create_task(executor.run(shutdown_task))

        # Let the system run
        await asyncio.sleep(0.2)
        shutdown_event.set()
        await executor_task

        # Verify the work item was executed
        service.execute_work_item.assert_called()
        call_args = service.execute_work_item.call_args
        assert call_args[0][0].work_item_id == "item-1"

    async def test_multiple_slots_process_items_concurrently(self):
        """Multiple slots can process different items at the same time."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Make execution take some time so we can verify concurrency
        execution_started = []

        async def track_execution(item, *args, **kwargs):
            execution_started.append(item.work_item_id)
            await asyncio.sleep(0.1)
            return True

        service.execute_work_item = AsyncMock(side_effect=track_execution)

        work_items = [make_work_item(f"item-{i}") for i in range(3)]
        # Make storage return items once, then empty
        call_count = 0

        def get_pending_ids(limit):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [item.work_item_id for item in work_items]
            return []

        storage.get_pending_work_item_ids = AsyncMock(side_effect=get_pending_ids)
        storage.get_work_items_by_ids.return_value = work_items

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
            1: SlotState(slot_id=1, status="idle"),
            2: SlotState(slot_id=2, status="idle"),
        }

        shutdown_event = asyncio.Event()

        # Start reader and multiple slot tasks
        reader_task = asyncio.create_task(
            executor._database_reader(shutdown_event, worker_interval=0.01)
        )
        slot_tasks = [
            asyncio.create_task(
                executor._slot_executor_task(i, shutdown_event, work_item_timeout=1.0)
            )
            for i in range(3)
        ]

        # Let the system run
        await asyncio.sleep(0.3)
        shutdown_event.set()
        await asyncio.gather(reader_task, *slot_tasks)

        # Verify all items were executed
        assert len(execution_started) == 3
        assert "item-0" in execution_started
        assert "item-1" in execution_started
        assert "item-2" in execution_started

    async def test_shutdown_stops_all_tasks_gracefully(self):
        """Shutdown event stops reader and slots gracefully."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Make storage return items continuously
        storage.get_pending_work_item_ids.return_value = []

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        executor.slot_manager.slots = {
            0: SlotState(slot_id=0, status="idle"),
        }

        shutdown_event = asyncio.Event()

        # Start tasks
        reader_task = asyncio.create_task(
            executor._database_reader(shutdown_event, worker_interval=0.1)
        )
        slot_task = asyncio.create_task(
            executor._slot_executor_task(0, shutdown_event, work_item_timeout=1.0)
        )

        # Let them run briefly
        await asyncio.sleep(0.05)

        # Trigger shutdown
        shutdown_event.set()

        # Wait for graceful shutdown
        await asyncio.gather(reader_task, slot_task)

        # If we get here without hanging, shutdown worked


class TestCrashHandling:
    """Tests for crash handling methods."""

    async def test_handle_database_reader_crash(self):
        """Reader crash increments counter."""
        service = make_mock_service()
        storage = make_mock_storage()
        executor = SlotExecutor(service.execute_work_item, storage=storage)

        # Create a mock crashed task
        crashed_task = Mock()
        crashed_task.exception.return_value = ValueError("Test crash")

        shutdown_event = asyncio.Event()
        initial_count = executor._reader_crash_count

        # Handle the crash
        new_task = executor._handle_reader_crash(crashed_task, shutdown_event)

        try:
            # Verify counter incremented
            assert executor._reader_crash_count == initial_count + 1
            # Verify new task was created
            assert new_task is not None
            assert new_task.get_name() == "work-items-db-reader"
            assert not new_task.done()
        finally:
            # Clean up
            new_task.cancel()

    async def test_handle_slot_crash(self):
        """Slot crash increments slot crash counter."""
        service = make_mock_service()
        storage = make_mock_storage()
        executor = SlotExecutor(service.execute_work_item, storage=storage)

        # Initialize a slot
        slot_id = 0
        executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)
        slot_state = executor.slot_manager.slots[slot_id]

        # Pretend that a WorkItem is running in this slot.
        slot_state.status = "executing"
        slot_state.work_item_id = "item-1"
        slot_state.task = Mock()

        # Create a mock crashed task
        crashed_task = Mock()
        crashed_task.exception.return_value = ValueError("Test crash")

        shutdown_event = asyncio.Event()

        initial_count = executor.slot_manager.slots[slot_id].crash_count

        # Handle the crash
        executor._handle_slot_crash(crashed_task, slot_id, shutdown_event)  # type: ignore[arg-type]

        # Verify the slot_state is reset
        slot_state = executor.slot_manager.slots[slot_id]
        assert slot_state.crash_count == initial_count + 1
        assert slot_state.status == "idle"
        assert slot_state.work_item_id is None

        # Verify that a new task was created and stored in the slot
        # The new task should be different from the crashed task
        assert slot_state.task is not None
        assert slot_state.task != crashed_task
        assert slot_state.task.get_name() == f"work-items-slot-{slot_id}"

        # Clean up
        slot_state.task.cancel()

    async def test_run_handles_reader_crash(self):
        """Main loop restarts reader task when it crashes."""
        service = make_mock_service()
        storage = make_mock_storage()
        quotas = make_mock_quotas(num_slots=1)

        # Make storage return no items
        storage.get_pending_work_item_ids.return_value = []

        executor = SlotExecutor(service.execute_work_item, storage=storage, quotas=quotas)

        # Track how many times reader is created
        reader_create_count = 0
        original_create_reader = executor._create_database_reader_task

        def counting_create_reader(executor_shutdown_event):
            nonlocal reader_create_count
            reader_create_count += 1
            return original_create_reader(executor_shutdown_event)

        executor._create_database_reader_task = counting_create_reader  # type: ignore[method-assign]

        # Make the reader crash once, then work normally
        crash_count = 0
        original_reader = executor._database_reader

        async def crashing_reader(shutdown_event, worker_interval):
            nonlocal crash_count
            crash_count += 1
            if crash_count == 1:
                # First call: crash immediately
                raise ValueError("Simulated reader crash")
            # Second call: run normally (will be stopped by shutdown)
            await original_reader(shutdown_event, worker_interval)

        executor._database_reader = crashing_reader

        # Create shutdown mechanism
        shutdown_event = asyncio.Event()
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Run briefly then shutdown
        async def delayed_shutdown():
            await asyncio.sleep(0.3)
            shutdown_event.set()

        asyncio.create_task(delayed_shutdown())  # noqa: RUF006

        await executor.run(shutdown_task)

        # Verify the reader was restarted
        assert executor._reader_crash_count == 1
        assert reader_create_count >= 2  # Initial + 1 restart

    async def test_run_handles_slot_crash(self):
        """Main loop restarts slot task when it crashes."""
        service = make_mock_service()
        storage = make_mock_storage()
        quotas = make_mock_quotas(num_slots=2)

        # Make storage return no items
        storage.get_pending_work_item_ids.return_value = []

        executor = SlotExecutor(service.execute_work_item, storage=storage, quotas=quotas)

        # Track how many times slot tasks are created
        slot_create_count = {0: 0, 1: 0}
        original_create_slot = executor._create_slot_task

        def counting_create_slot(slot_id, executor_shutdown_event):
            slot_create_count[slot_id] = slot_create_count.get(slot_id, 0) + 1
            return original_create_slot(slot_id, executor_shutdown_event)

        executor._create_slot_task = counting_create_slot  # type: ignore[method-assign]

        # Make slot 0 crash once, then work normally
        crash_count = defaultdict(int)
        original_slot_task = executor._slot_executor_task

        async def crashing_slot_task(slot_id, shutdown_event, work_item_timeout):
            crash_count[slot_id] = crash_count[slot_id] + 1
            if slot_id == 0 and crash_count[slot_id] == 1:
                # Slot 0, first call: crash immediately
                raise ValueError(f"Simulated slot {slot_id} crash")
            # All other cases: run normally
            await original_slot_task(slot_id, shutdown_event, work_item_timeout)

        executor._slot_executor_task = crashing_slot_task

        # Create shutdown mechanism
        shutdown_event = asyncio.Event()
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Run briefly then shutdown
        async def delayed_shutdown():
            await asyncio.sleep(0.3)
            shutdown_event.set()

        asyncio.create_task(delayed_shutdown())  # noqa: RUF006

        await executor.run(shutdown_task)

        # Verify slot 0 was restarted
        assert executor.slot_manager.slots[0].crash_count == 1
        assert slot_create_count[0] >= 2  # Initial + 1 restart
        # Slot 1 should not have crashed
        assert executor.slot_manager.slots[1].crash_count == 0
        assert slot_create_count[1] == 1  # Only initial

    async def test_run_handles_multiple_crashes(self):
        """Main loop handles multiple crashes of different tasks."""
        service = make_mock_service()
        storage = make_mock_storage()
        quotas = make_mock_quotas(num_slots=2)

        # Make storage return no items
        storage.get_pending_work_item_ids.return_value = []

        executor = SlotExecutor(service.execute_work_item, storage=storage, quotas=quotas)

        # Make both reader and slot crash once
        reader_crash_count = 0
        original_reader = executor._database_reader

        async def crashing_reader(shutdown_event, worker_interval):
            nonlocal reader_crash_count
            reader_crash_count += 1
            if reader_crash_count == 1:
                raise ValueError("Reader crash")
            await original_reader(shutdown_event, worker_interval)

        executor._database_reader = crashing_reader

        slot_crash_count = 0
        original_slot_task = executor._slot_executor_task

        async def crashing_slot_task(slot_id, shutdown_event, work_item_timeout):
            nonlocal slot_crash_count
            if slot_id == 1:
                slot_crash_count += 1
                if slot_crash_count == 1:
                    raise ValueError("Slot crash")
            await original_slot_task(slot_id, shutdown_event, work_item_timeout)

        executor._slot_executor_task = crashing_slot_task

        # Create shutdown mechanism
        shutdown_event = asyncio.Event()
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Run briefly then shutdown
        async def delayed_shutdown():
            await asyncio.sleep(0.4)
            shutdown_event.set()

        # We trigger the shutdown after a short delay so that our
        # slots and database reader have a chance to crash.
        asyncio.create_task(delayed_shutdown())  # noqa: RUF006

        await executor.run(shutdown_task)

        # Verify both were restarted
        assert executor._reader_crash_count == 1
        assert executor.slot_manager.slots[1].crash_count == 1


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_execute_cancels_task_on_timeout(self):
        """Execution cancels the task when timeout occurs."""
        service = make_mock_service()
        storage = make_mock_storage()

        # Create a task that would run forever
        cancel_called = asyncio.Event()

        # Call this function instead of the real execute_work_item function
        async def never_ending_execute(*args, **kwargs):
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancel_called.set()
                raise
            return True

        service.execute_work_item = AsyncMock(side_effect=never_ending_execute)

        executor = SlotExecutor(service.execute_work_item, storage=storage)
        slot_state = SlotState(slot_id=0, status="idle")
        work_item = make_work_item("item-1")

        await executor._execute_work_item_in_slot(work_item, slot_state, work_item_timeout=0.1)

        # Verify the task was cancelled
        assert cancel_called.is_set()
