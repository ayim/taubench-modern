"""Tests for slot resizing functionality in SlotExecutor."""

import asyncio
from contextlib import suppress
from types import MethodType
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadUserMessage
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.work_items.slot_executor import SlotExecutor, SlotState


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
    quotas.get_work_item_timeout_seconds = Mock(return_value=1)
    return quotas


class TestSlotResize:
    """Test suite for slot resizing functionality."""

    @pytest.fixture
    def executor(self):
        """Create a SlotExecutor with mocked dependencies."""

        async def mock_execute(item: WorkItem) -> bool:
            await asyncio.sleep(0.1)
            return True

        return SlotExecutor(
            execute_work_item=mock_execute,
            storage=make_mock_storage(),
            quotas=make_mock_quotas(),
        )

    async def test_resize_adds_slots_with_monotonic_ids(self, executor):
        """Test that scaling up creates new slots with monotonically increasing IDs."""
        # Create initial slots
        for _ in range(3):
            slot_id = next(executor.slot_manager._slot_id_counter)
            executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

        # Verify initial state: slots should have IDs 0, 1, 2
        assert list(sorted(executor.slot_manager.slots.keys())) == [0, 1, 2]

        # Create shutdown event for resize
        shutdown_event = asyncio.Event()

        try:
            # Scale up to 5 slots
            await executor._resize_slots(5, shutdown_event)

            # Verify we now have 5 slots with IDs 0, 1, 2, 3, 4
            assert len(executor.slot_manager.slots) == 5
            assert list(sorted(executor.slot_manager.slots.keys())) == [0, 1, 2, 3, 4]
        finally:
            # Signal shutdown and cleanup tasks
            shutdown_event.set()
            tasks_to_cancel = [
                slot.slot_task
                for slot in executor.slot_manager.slots.values()
                if slot.slot_task and not slot.slot_task.done()
            ]
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    async def test_resize_removes_only_idle_slots(self, executor):
        """Test that scaling down only removes idle slots, not busy ones."""
        shutdown_event = asyncio.Event()

        # Create 5 slots
        for _ in range(5):
            slot_id = next(executor.slot_manager._slot_id_counter)
            executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id, status="idle")

        # Mark slots 1 and 3 as executing (busy)
        executor.slot_manager.slots[1].status = "executing"
        executor.slot_manager.slots[3].status = "executing"

        # Try to scale down to 2 slots - will try to remove 3 slots
        # It will remove the 3 idle slots (0, 2, 4) and keep the 2 busy ones (1, 3)
        await executor._resize_slots(2, shutdown_event)

        # Should only remove idle slots, so we expect 2 slots remaining
        # (only the busy slots remain)
        assert len(executor.slot_manager.slots) == 2

        # Verify busy slots are still there
        assert 1 in executor.slot_manager.slots
        assert 3 in executor.slot_manager.slots

        # Note: No cleanup needed here since no tasks were created (slots created manually)

    async def test_resize_ids_remain_monotonic_after_removal(self, executor):
        """Test that slot IDs remain monotonic even after removing slots."""
        shutdown_event = asyncio.Event()

        try:
            # Create 5 slots (IDs 0-4)
            for _ in range(5):
                slot_id = next(executor.slot_manager._slot_id_counter)
                executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

            assert list(sorted(executor.slot_manager.slots.keys())) == [0, 1, 2, 3, 4]

            # Scale down to 2 slots - removes first 3 idle slots (0, 1, 2), leaves 3, 4
            await executor._resize_slots(2, shutdown_event)
            assert len(executor.slot_manager.slots) == 2
            assert list(sorted(executor.slot_manager.slots.keys())) == [3, 4]

            # Now scale back up to 5 slots - adds 3 new slots
            await executor._resize_slots(5, shutdown_event)
            assert len(executor.slot_manager.slots) == 5

            # New slots should have IDs 5, 6, 7 (continuing from where we left off)
            slot_ids = sorted(executor.slot_manager.slots.keys())
            # We should have the 2 that remained (3, 4) plus 3 new ones (5, 6, 7)
            assert slot_ids == [3, 4, 5, 6, 7]

            # Verify no duplicate IDs exist
            assert len(slot_ids) == len(set(slot_ids))
        finally:
            # Signal shutdown and cleanup tasks
            shutdown_event.set()
            tasks_to_cancel = [
                slot.slot_task
                for slot in executor.slot_manager.slots.values()
                if slot.slot_task and not slot.slot_task.done()
            ]
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    async def test_resize_partial_removal_when_slots_busy(self, executor, caplog):
        """Test that we get appropriate logging when we can't remove all desired slots."""
        import logging

        caplog.set_level(logging.INFO)

        shutdown_event = asyncio.Event()

        try:
            # Create 5 slots
            for _ in range(5):
                slot_id = next(executor.slot_manager._slot_id_counter)
                executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

            # Mark 3 slots as busy
            executor.slot_manager.slots[0].status = "executing"
            executor.slot_manager.slots[2].status = "executing"
            executor.slot_manager.slots[4].status = "executing"

            # Try to scale down to 1 slot
            await executor._resize_slots(1, shutdown_event)

            # Should only remove 2 idle slots (1 and 3)
            assert len(executor.slot_manager.slots) == 3

            # Check for log message about partial removal
            partial_messages = [rec for rec in caplog.records if "still busy" in rec.message]
            assert len(partial_messages) == 1
            assert "Could only remove 2 of 4 slots" in partial_messages[0].message
        finally:
            # Signal shutdown and cleanup tasks
            shutdown_event.set()
            tasks_to_cancel = [
                slot.slot_task
                for slot in executor.slot_manager.slots.values()
                if slot.slot_task and not slot.slot_task.done()
            ]
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    async def test_resize_does_not_cancel_slot_with_inflight_work_item(self):
        """Resizing down should not drop an item that is already dequeued."""
        execute_called = asyncio.Event()

        # Fake the work-item execution Function
        async def execute_work_item(item: WorkItem) -> bool:
            execute_called.set()
            return True

        executor = SlotExecutor(
            execute_work_item=execute_work_item,
            storage=make_mock_storage(),
            quotas=make_mock_quotas(1),
        )

        shutdown_event = asyncio.Event()
        slot_id = executor.slot_manager.next_slot_id()
        executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

        # Gate work-item execution so we can resize after the item is dequeued but before it runs.
        queued_event = asyncio.Event()
        release_event = asyncio.Event()
        original_execute = executor._execute_work_item_in_slot

        async def gated_execute_work_item(
            self, item: WorkItem, slot_state: SlotState, timeout: float
        ) -> None:
            queued_event.set()
            await release_event.wait()
            await original_execute(item, slot_state, timeout)

        executor._execute_work_item_in_slot = MethodType(gated_execute_work_item, executor)

        slot_task = executor._create_slot_task(slot_id, shutdown_event)

        try:
            # Queue a work-item
            work_item = make_work_item()
            await executor._work_queue.put(work_item)

            # Wait until the slot has dequeued the item and is waiting for the release event.
            await asyncio.wait_for(queued_event.wait(), 1.0)

            # Attempt to resize down to zero slots while the slot still appears idle.
            await executor._resize_slots(0, shutdown_event)

            # Allow execution to continue and ensure the work item was actually processed.
            release_event.set()
            await asyncio.wait_for(execute_called.wait(), 1.0)
        finally:
            release_event.set()
            shutdown_event.set()
            if slot_task and not slot_task.done():
                with suppress(asyncio.CancelledError):
                    await asyncio.wait_for(slot_task, 1.0)

    async def test_resize_no_change_when_already_at_target(self, executor):
        """Test that no changes occur when already at target size."""
        shutdown_event = asyncio.Event()

        # Create 3 slots
        for _ in range(3):
            slot_id = next(executor.slot_manager._slot_id_counter)
            executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

        initial_slots = dict(executor.slot_manager.slots)

        # "Resize" to same size
        await executor._resize_slots(3, shutdown_event)

        # No changes should have occurred
        assert executor.slot_manager.slots == initial_slots

        # Note: No cleanup needed here since no tasks were created (slots created manually)

    async def test_resize_scale_down_after_slot_processed_work(self, executor):
        """Scaling down after a slot processed work should still cancel its task."""
        shutdown_event = asyncio.Event()
        slot_id = executor.slot_manager.next_slot_id()
        executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id, status="idle")
        slot_task = executor._create_slot_task(slot_id, shutdown_event)

        work_item = make_work_item("item-resize")
        await executor._work_queue.put(work_item)

        async def wait_for_slot_idle():
            for _ in range(200):
                slot_state = executor.slot_manager.slots[slot_id]
                is_idle = (
                    slot_state.status == "idle"
                    and slot_state.work_item_id is None
                    and executor._work_queue.empty()
                )
                if is_idle:
                    return
                await asyncio.sleep(0.01)
            raise AssertionError("Slot did not process queued work item before resize")

        await wait_for_slot_idle()
        slot_state = executor.slot_manager.slots[slot_id]
        assert slot_state.status == "idle", "Slot should be idle after work item"
        assert slot_state.work_item_task is None, (
            "Work item task reference should be cleared after work item"
        )

        try:
            await executor._resize_slots(0, shutdown_event)
            assert slot_task.done(), (
                "Resize should cancel the long-running slot task for an idle slot"
            )
        finally:
            if not slot_task.done():
                slot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await slot_task

    async def test_resize_scale_up_creates_new_slots(self, executor):
        """Scaling up should create new slots with tasks."""
        # Create 2 initial slots using the slot manager's counter
        shutdown_event = asyncio.Event()
        for _ in range(2):
            slot_id = executor.slot_manager.next_slot_id()
            executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id, status="idle")
            executor._create_slot_task(slot_id, shutdown_event)

        # Verify we have 2 slots
        assert len(executor.slot_manager.slots) == 2

        # Scale up to 5 slots
        await executor._resize_slots(5, shutdown_event)

        # Verify we now have 5 slots
        assert len(executor.slot_manager.slots) == 5

        # Verify all slots have tasks
        for slot_state in executor.slot_manager.slots.values():
            assert slot_state.slot_task is not None
            assert not slot_state.slot_task.done()

        # Clean up all slots
        for slot_state in executor.slot_manager.slots.values():
            if slot_state.slot_task and not slot_state.slot_task.done():
                slot_state.slot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await slot_state.slot_task

    async def test_resize_scale_down_skipped_when_work_queue_has_items(self, executor):
        """Test that scale down is skipped when work queue has pending items."""
        shutdown_event = asyncio.Event()

        # Create 5 slots
        for _ in range(5):
            slot_id = next(executor.slot_manager._slot_id_counter)
            executor.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id, status="idle")

        # Add work items to the queue
        work_item_1 = make_work_item("item-1")
        work_item_2 = make_work_item("item-2")
        work_item_3 = make_work_item("item-3")
        await executor._work_queue.put(work_item_1)
        await executor._work_queue.put(work_item_2)
        await executor._work_queue.put(work_item_3)

        # Verify queue is not empty
        assert not executor._work_queue.empty()
        initial_qsize = executor._work_queue.qsize()
        assert initial_qsize == 3

        # Try to scale down to 2 slots - should be skipped
        await executor._resize_slots(2, shutdown_event)

        # Verify no slots were removed
        assert len(executor.slot_manager.slots) == 5

        # Verify queue still has all items
        assert executor._work_queue.qsize() == initial_qsize

    async def test_resize_scale_up_slot(self):
        """verify crash detection when a newly scaled-up slot crashes immediately."""
        # Create executor with simple static quotas
        executor = SlotExecutor(
            execute_work_item=AsyncMock(return_value=True),
            storage=make_mock_storage(),
            quotas=make_mock_quotas(num_slots=2),
        )

        # Track crashes - slot_id=1 crashes only once, then behaves normally
        crash_count = {"slot_1": 0}

        # Mock the slot executor task to crash for slot_id=1 on first invocation only
        async def fake_slot_executor_task(
            self, slot_id: int, shutdown_event: asyncio.Event
        ) -> None:
            if slot_id == 1 and crash_count["slot_1"] == 0:
                # This slot crashes immediately on first invocation
                crash_count["slot_1"] += 1
                raise RuntimeError("test crash on scale-up")
            # After crash or for other slots, wait for shutdown normally
            await shutdown_event.wait()

        executor._slot_executor_task = MethodType(fake_slot_executor_task, executor)

        # Set up shutdown mechanism and start executor
        global_shutdown_event = asyncio.Event()
        global_shutdown_task = asyncio.create_task(global_shutdown_event.wait())
        run_task = asyncio.create_task(executor.run(global_shutdown_task))

        try:
            # Wait for both slots to be created during run() initialization
            # The executor.run() creates all slots upfront based on quotas
            await asyncio.sleep(0.1)

            # Wait for slot_id=1 to crash and be restarted
            # Poll for the crash to be detected and the slot restarted
            crash_detected = False
            for _ in range(100):
                slot_state = executor.slot_manager.slots.get(1)
                if slot_state and slot_state.crash_count >= 1:
                    # Crash was detected and slot restarted
                    crash_detected = True
                    # Verify the crashed slot has been restarted
                    assert slot_state.crash_count >= 1, "Crash count should be incremented"
                    assert slot_state.slot_task is not None, "Slot should have a new task"
                    assert not slot_state.slot_task.done(), "New slot task should be running"
                    break
                await asyncio.sleep(0.01)

            # Verify crash was detected
            assert crash_detected, "Slot crash should have been detected and slot restarted"

        finally:
            # Clean shutdown
            global_shutdown_event.set()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(run_task, timeout=1.0)
            await global_shutdown_task
