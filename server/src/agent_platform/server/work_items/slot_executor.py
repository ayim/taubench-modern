"""
Slot Executor - Handles slot-based work item execution.

This module contains the SlotExecutor class which manages slot-based
execution of work items, maintaining N execution slots that process
work items as they become available.
"""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from itertools import count
from typing import Literal

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage import BaseStorage, StorageService
from agent_platform.server.work_items.executor import WorkItemExecutor
from agent_platform.server.work_items.service import WorkItemTaskStatus

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "work-items"


@dataclass
class SlotState:
    """State tracking for a single execution slot."""

    slot_id: int
    """ The unique ID for this slot."""
    status: Literal["idle", "executing"] = "idle"
    """ The current status of this slot."""
    work_item_id: str | None = None
    """ The ID of the work item currently being executed by this slot."""
    slot_task: asyncio.Task | None = None
    """ The long-running task for the slot executor."""
    work_item_task: asyncio.Task | None = None
    """ The short-running task for a work item execution."""
    crash_count: int = 0
    """ The number of times a work_item task has crashed during execution."""


@dataclass
class SlotManager:
    """Manages the state of all execution slots."""

    slots: dict[int, SlotState] = field(default_factory=dict)
    _slot_id_counter: count = field(default_factory=count)

    def next_slot_id(self) -> int:
        """Return the next available slot ID."""
        return next(self._slot_id_counter)

    def get_num_free_slots(self) -> int:
        """Return the number of slots that are currently idle."""
        return sum(1 for slot in self.slots.values() if slot.status == "idle")

    def get_slot_status(self) -> list[WorkItemTaskStatus]:
        """Return current status of all slots for internal API."""
        return [
            WorkItemTaskStatus(
                task_id=slot.slot_id,
                status=slot.status,
                work_item_id=slot.work_item_id,
            )
            for slot in self.slots.values()
        ]

    def get_slot_tasks(self) -> list[asyncio.Task]:
        """Return all active slot tasks."""
        return [slot.slot_task for slot in self.slots.values() if slot.slot_task is not None]


async def _cancel_tasks_with_timeout(
    tasks: list[asyncio.Task] | set[asyncio.Task],
    timeout_seconds: float,
) -> None:
    """
    Cancel a collection of tasks and wait for them to complete.

    Args:
        tasks: Collection of asyncio Tasks to cancel
        timeout_seconds: Timeout in seconds to wait for tasks to complete.
                If timeout is exceeded, a warning is logged.
    """
    if not tasks:
        return

    # Cancel all tasks
    for task in tasks:
        if not task.done():
            task.cancel()

    # Wait for all tasks to complete
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            f"Timeout waiting for {len(tasks)} tasks to complete cancellation ({timeout_seconds}s)"
        )


class SlotExecutor:
    """
    Executor for slot-based work item processing.

    Slot-based mode maintains N execution slots that continuously process
    work items as they become available from the database. This provides
    better resource utilization and lower latency than batch mode.
    """

    def __init__(
        self,
        execute_work_item: WorkItemExecutor,
        storage: BaseStorage | None = None,
        quotas: QuotasService | None = None,
    ):
        """
        Initialize the SlotExecutor.

        Args:
            execute_work_item: Function that executes a work item
            storage: Optional StorageService instance for testing
            quotas: Optional QuotasService instance for testing
        """
        self.execute_work_item: WorkItemExecutor = execute_work_item
        self.slot_manager = SlotManager()
        self._storage = storage or StorageService.get_instance()
        self._quotas: QuotasService | None = quotas
        self._work_queue: asyncio.Queue[WorkItem] = asyncio.Queue()
        self._reader_crash_count: int = 0
        self.reader_task: asyncio.Task | None = None
        self._resize_cancelled_tasks: set[asyncio.Task] = set()
        self._task_update_event: asyncio.Event | None = None

    async def quotas(self) -> QuotasService:
        """Get the QuotasService instance."""
        if self._quotas is None:
            self._quotas = await QuotasService.get_instance()
        return self._quotas

    def get_slot_status(self) -> list[WorkItemTaskStatus]:
        return self.slot_manager.get_slot_status()

    def _find_slot_id_for_task(self, task: asyncio.Task) -> int | None:
        """
        Find the slot ID for a given task.

        Args:
            task: The task to find the slot ID for

        Returns:
            The slot ID if found, None otherwise
        """
        for slot_id, slot_state in self.slot_manager.slots.items():
            if slot_state.slot_task == task:
                return slot_id
        return None

    def _create_database_reader_task(
        self,
        executor_shutdown_event: asyncio.Event,
    ) -> asyncio.Task:
        """
        Create a database reader task.

        Args:
            executor_shutdown_event: Event for coordinating shutdown

        Returns:
            The created task
        """
        from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

        task = asyncio.create_task(
            self._database_reader(executor_shutdown_event, WORK_ITEMS_SETTINGS.worker_interval)
        )
        task.set_name("work-items-db-reader")
        return task

    def _create_slot_task(
        self,
        slot_id: int,
        executor_shutdown_event: asyncio.Event,
    ) -> asyncio.Task:
        """
        Create a slot executor task and store it in the slot's state.

        Args:
            slot_id: The slot ID for this task
            executor_shutdown_event: Event for coordinating shutdown

        Returns:
            The created task
        """
        task = asyncio.create_task(
            self._slot_executor_task(
                slot_id,
                executor_shutdown_event,
            )
        )
        task.set_name(f"work-items-slot-{slot_id}")
        self.slot_manager.slots[slot_id].slot_task = task
        self._notify_task_update()
        return task

    def _notify_task_update(self) -> None:
        """Signal the run loop that a new task was added."""
        if self._task_update_event is not None:
            self._task_update_event.set()

    def _handle_reader_crash(
        self,
        crashed_task: asyncio.Task,
        executor_shutdown_event: asyncio.Event,
    ) -> asyncio.Task:
        """
        Handle a database reader task crash.

        Increments the crash counter, logs the error, and creates a new reader task.

        Args:
            crashed_task: The crashed reader task
            executor_shutdown_event: Event for coordinating shutdown

        Returns:
            The newly created reader task
        """
        self._reader_crash_count += 1

        # We never call .cancel() on the DB reader task, so the only possible way
        # for it to complete is for an uncaught Exception to be raised.
        exception = crashed_task.exception()
        logger.error(
            f"WorkItems: Database reader task crashed "
            f"(restart #{self._reader_crash_count}): {exception}",
            exc_info=exception,
        )

        # Restart the reader task
        reader_task = self._create_database_reader_task(executor_shutdown_event)
        logger.info(f"Restarted database reader task (restart #{self._reader_crash_count})")
        return reader_task

    def _handle_slot_crash(
        self,
        crashed_task: asyncio.Task,
        slot_id: int,
        executor_shutdown_event: asyncio.Event,
    ) -> None:
        """
        Handle a slot task crash.

        Increments the slot crash counter, logs the error, and creates a new slot task.

        Args:
            crashed_task: The crashed slot task
            slot_id: The slot ID for this task
            executor_shutdown_event: Event for coordinating shutdown
        """
        slot_state = self.slot_manager.slots[slot_id]
        slot_state.crash_count += 1
        slot_state.status = "idle"
        slot_state.work_item_id = None
        slot_state.slot_task = None

        # We never call .cancel() on the Slot task in the normal course of events.
        # We do call .cancel() on the Slot task when we resize the slots, but handle
        # that in a higher-level. So the only possible way us to be here is for an uncaught
        # Exception to be raised.
        exception = crashed_task.exception()
        logger.error(
            f"WorkItems: Slot {slot_id} task crashed "
            f"(restart #{slot_state.crash_count}): {exception}",
            exc_info=exception,
        )

        # Restart the slot task
        self._create_slot_task(
            slot_id,
            executor_shutdown_event,
        )

        logger.info(f"Restarted slot {slot_id} task (restart #{slot_state.crash_count})")

    async def _handle_completed_task(
        self,
        task: asyncio.Task,
        executor_shutdown_event: asyncio.Event,
    ) -> None:
        """Handle a worker task that completed while the service is running."""
        if task == self.reader_task:
            # Database reader crashed which should not happen in normal operation.
            # Restart it.
            self.reader_task = self._handle_reader_crash(task, executor_shutdown_event)
            return

        if task in self._resize_cancelled_tasks:
            # Slot task intentionally cancelled by resize - do not restart it.
            self._resize_cancelled_tasks.discard(task)
            logger.debug(f"Slot task {task.get_name()} completed after resize")
            return

        maybe_slot_id = self._find_slot_id_for_task(task)
        if maybe_slot_id is not None:
            # Slots removed during resize are popped from the manager, so None means already removed
            self._handle_slot_crash(task, maybe_slot_id, executor_shutdown_event)
            return

        logger.error(f"Unknown task completed: {task.get_name()}")

    async def run(self, global_shutdown_task: asyncio.Task) -> None:
        """
        Run the work items service in slot-based execution mode.

        Slot-based mode runs continuously until shutdown, maintaining N execution slots
        that process work items as they become available.

        Args:
            shutdown_task: The shutdown task to wait on for shutdown coordination
        """
        num_slots = (await self.quotas()).get_max_parallel_work_items_in_process()

        logger.info(f"Initializing slot-based execution with {num_slots} slots")
        for _ in range(num_slots):
            slot_id = self.slot_manager.next_slot_id()
            self.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)

        # Create shutdown event for coordinating task shutdown
        executor_shutdown_event = asyncio.Event()

        # Start database reader task
        self.reader_task = self._create_database_reader_task(executor_shutdown_event)

        # Start slot executor tasks
        for slot_id in range(num_slots):
            self._create_slot_task(
                slot_id,
                executor_shutdown_event,
            )

        self._task_update_event = asyncio.Event()

        # Main execution loop: wait for shutdown or handle task crashes
        try:
            while True:
                # Long block -- waiting for any task to complete. Blocking might exit because of:
                #   1. unhandled crash
                #   2. slot resize to a smaller number of slots
                #   3. shutdown requested
                #   4. tasks scaled up
                slot_tasks = self.slot_manager.get_slot_tasks()
                task_update_waiter = asyncio.create_task(self._task_update_event.wait())
                all_tasks = [
                    global_shutdown_task,
                    self.reader_task,
                    task_update_waiter,
                    *slot_tasks,
                ]
                done, pending = await asyncio.wait(
                    all_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if task_update_waiter in done:
                    done.remove(task_update_waiter)
                    self._task_update_event.clear()
                    if not done:
                        # No completed worker tasks to process; rebuild wait set.
                        continue
                else:
                    task_update_waiter.cancel()
                    with suppress(asyncio.CancelledError):
                        await task_update_waiter

                # Check if shutdown was requested
                if global_shutdown_task in done:
                    logger.info("Shutdown requested, stopping slot-based execution")
                    break
                logger.info("Slot-based execution loop completed, checking for completed tasks")

                # Handle crashed tasks - restart them individually
                for task in done:
                    await self._handle_completed_task(task, executor_shutdown_event)

        finally:
            # Signal shutdown to all worker tasks
            executor_shutdown_event.set()
            if self._task_update_event is not None:
                self._task_update_event.set()

            # Gracefully shutdown all worker tasks
            slot_tasks = self.slot_manager.get_slot_tasks()
            await self._graceful_shutdown(self.reader_task, slot_tasks)

        logger.info("Work Items SlotExecutor shutdown completed")

    async def _graceful_shutdown(
        self,
        reader_task: asyncio.Task | None,
        slot_tasks: list[asyncio.Task],
    ) -> None:
        """
        After the caller has requested a shutdown, wait for the db reader and slot tasks
        to complete, cancelling them if they don't complete within a timeout.

        This method attempts to gracefully shutdown all tasks with a timeout,
        and if that fails, cancels them and waits for cancellation to complete.

        Args:
            reader_task: The database reader task to shut down
            slot_tasks: List of slot executor tasks to shut down
        """
        # Wait for all worker tasks to complete gracefully
        graceful_shutdown_timeout = 30.0
        queue_drain = asyncio.create_task(self._return_queue_to_pool())

        # Build the list of tasks to wait for
        tasks_to_wait = [*slot_tasks, queue_drain]
        if reader_task is not None:
            tasks_to_wait.append(reader_task)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks_to_wait, return_exceptions=True),
                timeout=graceful_shutdown_timeout,
            )
            for result in results:
                if result is not None:
                    logger.error(f"Work Items task failed on shutdown: {result}")
        except TimeoutError:
            logger.error("Work Items SlotExecutor shutdown timed out, cancelling tasks")

            # Cancel all of the internal tasks and give them a few seconds to clean up.
            await _cancel_tasks_with_timeout(tasks_to_wait, 5.0)

    async def _collect_idle_slots(self, num_to_remove: int) -> list[int]:
        """Fetches no more than num_to_remove idle slots."""
        tasks_to_cancel: list[int] = []

        for slot_id, slot in self.slot_manager.slots.items():
            if len(tasks_to_cancel) >= num_to_remove:
                break

            if slot.status == "idle":
                tasks_to_cancel.append(slot_id)

        return tasks_to_cancel

    async def _resize_slots(
        self, new_num_slots: int, executor_shutdown_event: asyncio.Event
    ) -> None:
        """
        Resize the slots to the new number of slots.

        When scaling up, new slots are added and tasks are created immediately.
        When scaling down, only idle slots are removed; busy slots remain until
        they become idle on a future iteration.

        Warning: This algorithm requires that no additional WorkItems be made available
        to the Slots. Slots which are idle must not be allowed to become executing,
        else, this algorithm is not thread-safe.

        Args:
            new_num_slots: Target number of slots
            executor_shutdown_event: Event for coordinating shutdown with new tasks
        """
        current_num_slots = len(self.slot_manager.slots)
        logger.info(f"Attempting to resize slots from {current_num_slots} to {new_num_slots}")

        if new_num_slots > current_num_slots:
            # Scaling up: add new slots and create tasks for them
            num_to_add = new_num_slots - current_num_slots
            for _ in range(num_to_add):
                slot_id = next(self.slot_manager._slot_id_counter)
                self.slot_manager.slots[slot_id] = SlotState(slot_id=slot_id)
                self._create_slot_task(slot_id, executor_shutdown_event)
                logger.info(f"Added slot {slot_id} (scaling to {new_num_slots})")

        elif new_num_slots < current_num_slots:
            if not self._work_queue.empty():
                logger.info("Latent work items in queue, skipping this scale down")
                return

            # Scaling down: remove idle slots until we reach target size
            num_to_remove = current_num_slots - new_num_slots

            # Collect all idle slots to remove
            slots_to_remove = await self._collect_idle_slots(num_to_remove)
            # Get all of the corresponding tasks
            tasks_to_cancel: list[asyncio.Task] = []
            for slot_id in slots_to_remove:
                task = self.slot_manager.slots[slot_id].slot_task
                # Collect all the tasks and cancel them so we can await them all at once.
                if task is not None:  # should always be true
                    task.cancel()
                    tasks_to_cancel.append(task)
                    # Track this task as intentionally cancelled for resize
                    self._resize_cancelled_tasks.add(task)

            # Await all cancelled tasks concurrently
            if tasks_to_cancel:
                logger.info(
                    f"Waiting for {len(tasks_to_cancel)} slot cancellations to complete "
                    "before cleanup"
                )
                # Intentionally ignoring the return.
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

            # Remove all the slots that now have their tasks stopped.
            for slot_id in slots_to_remove:
                self.slot_manager.slots.pop(slot_id)
                logger.info(f"Removed idle slot {slot_id} (scaling to {new_num_slots})")

            removed_count = len(slots_to_remove)
            if removed_count < num_to_remove:
                logger.info(
                    f"Could only remove {removed_count} of {num_to_remove} slots - "
                    f"{num_to_remove - removed_count} slots still busy"
                )

        # else, do nothing - already at target size

    async def _return_queue_to_pool(self) -> None:
        """
        Returns any work items that were in the queue to the pool. This
        should generally be a no-op because we never queue items unless we have
        open slots, but there is a chance that we read the queue before a slot
        can read the queue.
        """
        while not self._work_queue.empty():
            item = await self._work_queue.get()
            logger.info(f"Returning item {item.work_item_id} from queue to the pool on shutdown")
            success = await self._storage.return_work_item_to_pool(item.work_item_id)
            if not success:
                logger.warning(f"Failed to return item {item.work_item_id} to the pool on shutdown")

    async def _execute_work_item_in_slot(
        self,
        item: "WorkItem",
        slot_state: SlotState,
        work_item_timeout: float,
    ) -> None:
        """
        Execute a single work item in a slot with timeout handling.

        This method handles the lifecycle of executing one work item after the slot
        has already marked itself as executing:
        - Execute the work item with timeout
        - Handle timeout and errors
        - Mark slot as idle

        Args:
            item: The work item to execute
            slot_state: The slot state to update
            work_item_timeout: Timeout for the work item execution
        """
        # Slot should already be executing when this is called, but normalize if needed.
        if slot_state.status != "executing":
            slot_state.status = "executing"
        if slot_state.work_item_id not in (None, item.work_item_id):
            logger.warning(
                "Slot %s executing unexpected work item %s (state has %s)",
                slot_state.slot_id,
                item.work_item_id,
                slot_state.work_item_id,
            )
        slot_state.work_item_id = item.work_item_id
        slot_id = slot_state.slot_id

        logger.info(
            f"Slot {slot_id} executing work item {item.work_item_id} (timeout {work_item_timeout}s)"
        )

        try:
            # Create the execution task and store it for potential cancellation
            # Note: execute_work_item is typed as Awaitable but returns a Coroutine at runtime
            slot_state.work_item_task = asyncio.create_task(self.execute_work_item(item))  # type: ignore[arg-type]

            await asyncio.wait_for(slot_state.work_item_task, timeout=work_item_timeout)

            logger.info(f"Slot {slot_id} completed work item {item.work_item_id} normally")

        except TimeoutError:
            # Work item timed out
            logger.error(
                f"Slot {slot_id} work item {item.work_item_id} timed out after "
                f"{work_item_timeout}s, marking as ERROR"
            )

            # Cancel the task
            if slot_state.work_item_task and not slot_state.work_item_task.done():
                slot_state.work_item_task.cancel()
                with suppress(asyncio.CancelledError):
                    await slot_state.work_item_task

            # Mark as error in database
            await self._storage.mark_incomplete_work_items_as_error([item.work_item_id])

        except Exception as exc:
            # Something unexpected happened in execution of this WorkItem. The WorkItem
            # should have been marked as ERROR in the database by the time we get here,
            # but we'll do it again just to be sure.
            logger.error(
                f"Slot {slot_id} error executing work item {item.work_item_id}: {exc}",
                exc_info=exc,
            )

            # Mark as error in database if it's still in PENDING/EXECUTING state
            await self._storage.mark_incomplete_work_items_as_error([item.work_item_id])

        finally:
            # Mark slot as idle again
            slot_state.status = "idle"
            slot_state.work_item_id = None
            slot_state.work_item_task = None

    async def _return_work_item_to_pool_on_shutdown(self, item: WorkItem, slot_id: int) -> None:
        """
        Return a work item to the pool when shutting down.

        We picked up an item, but we're now shutting down. We should have exclusive
        ownership (EXECUTING), so we should return it back to the pool (PENDING).
        Double check the current status to minimize the risk of a race.

        Args:
            item: The work item to return to the pool
            slot_id: The slot ID for logging purposes
        """
        current_item = await self._storage.get_work_item(item.work_item_id)
        if current_item and current_item.status == WorkItemStatus.EXECUTING:
            logger.info(
                f"Slot {slot_id} picked up an item that is in EXECUTING state "
                f"but is shutting down. Returning it to the pool (PENDING)."
            )
            returned = await self._storage.return_work_item_to_pool(
                item.work_item_id,
            )
            if not returned:
                logger.error(
                    f"Slot {slot_id} failed to return item {item.work_item_id} "
                    f"to the pool (PENDING). {current_item.model_dump()!r}"
                )

    async def _slot_executor_task(
        self,
        slot_id: int,
        shutdown_event: asyncio.Event,
    ) -> None:
        """
        The main loop of a single slot executor task with timeout handling.

        This is a long-running task that loops: fetch work from queue → execute → repeat.

        Args:
            slot_id: Unique identifier for this slot
            work_queue: Queue to fetch work items from
            slot_manager: Manager to update slot state
            shutdown_event: Event signaling shutdown
            work_item_timeout: Timeout for individual work items
        """
        slot_state = self.slot_manager.slots[slot_id]
        quotas_service = await self.quotas()

        logger.info(f"Work Items Slot Executor {slot_id} started")

        while not shutdown_event.is_set():
            get_task: asyncio.Task | None = None
            shutdown_task: asyncio.Task | None = None
            try:
                # Wait for work item from queue or shutdown signal
                # Use wait() to allow shutdown to interrupt the queue wait
                get_task = asyncio.create_task(self._work_queue.get())
                shutdown_task = asyncio.create_task(shutdown_event.wait())

                done, pending = await asyncio.wait(
                    [get_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
                )
                work_item: WorkItem | None = None

                if get_task in done and not get_task.cancelled():
                    work_item = get_task.result()
                    assert work_item is not None  # should never happen

                    # Mark slot as executing immediately so resize logic won't treat it as idle.
                    slot_state.status = "executing"
                    slot_state.work_item_id = work_item.work_item_id

                # Cancel pending tasks and wait for them all to complete within 5 seconds
                await _cancel_tasks_with_timeout(list(pending), 5.0)

                # Check if shutdown was signaled
                if shutdown_event.is_set():
                    # If we got an item, put it back. Then, return.
                    if work_item is not None:
                        try:
                            await self._return_work_item_to_pool_on_shutdown(work_item, slot_id)
                        except Exception as exc:
                            logger.error(
                                f"Slot {slot_id} error picking up item: {exc}", exc_info=exc
                            )
                        finally:
                            slot_state.status = "idle"
                            slot_state.work_item_id = None
                    return

                # Else, pick the item off the queue
                if work_item is None:
                    continue

                # Check the current timeout just before we start running it.
                work_item_timeout = quotas_service.get_work_item_timeout_seconds()

                # Actually run the work item!
                await self._execute_work_item_in_slot(work_item, slot_state, work_item_timeout)

            except asyncio.CancelledError:
                # _slot_executor_task was cancelled, make sure we clean up the tasks
                # that we might have.
                tasks_to_cancel = [
                    t for t in [get_task, shutdown_task] if t is not None and not t.done()
                ]
                await self._handle_slot_cancelled(slot_id, slot_state, tasks_to_cancel)
                return
            except Exception as exc:
                logger.error(f"Slot {slot_id} unexpected error: {exc}", exc_info=exc)
                # Mark as error in database if it's still in PENDING/EXECUTING state
                if slot_state.work_item_id:
                    await self._storage.mark_incomplete_work_items_as_error(
                        [slot_state.work_item_id]
                    )

                # Continue running even if there's an error
                slot_state.status = "idle"
                slot_state.work_item_id = None
                slot_state.work_item_task = None

    async def _handle_slot_cancelled(
        self,
        slot_id: int,
        slot_state: SlotState,
        inner_tasks: list[asyncio.Task],
    ) -> None:
        """Cleanup helper when a slot executor task is cancelled."""
        logger.info(f"Slot {slot_id} cancelled, shutting down ({slot_state.work_item_id})")

        # Cancel any outstanding wait tasks within 5 seconds
        await _cancel_tasks_with_timeout(inner_tasks, 5.0)

        # Cancel in-flight work item, if any
        if slot_state.work_item_task and not slot_state.work_item_task.done():
            slot_state.work_item_task.cancel()
            with suppress(asyncio.CancelledError):
                await slot_state.work_item_task

        # Mark as error in database if the WorkItem is still in progress. We can't safely
        # ascertain if it is "safe" for another slot to pick up this work item and continue
        # processing it, so we mark it as ERROR to be safe.
        if slot_state.work_item_id:
            await self._storage.mark_incomplete_work_items_as_error([slot_state.work_item_id])

    async def _fetch_and_queue_work_items(self) -> None:
        """Fetch pending work items from storage and queue them for execution."""
        # Calculate how many slots are currently free
        num_free_slots = self.slot_manager.get_num_free_slots()
        slots_to_fill = num_free_slots - self._work_queue.qsize()

        if slots_to_fill > 0:
            # Fetch ONLY as many work items as we have free slots
            work_item_ids = await self._storage.get_pending_work_item_ids(slots_to_fill)

            if work_item_ids:
                logger.info(
                    f"Database reader found {len(work_item_ids)} work items: {work_item_ids!r}"
                )
                # Fetch full work item objects
                items = await self._storage.get_work_items_by_ids(work_item_ids)

                # Put them on the queue for slots to pick up
                for item in items:
                    await self._work_queue.put(item)
                    logger.debug(f"Queued work item {item.work_item_id} for execution")
            else:
                logger.debug("No pending work items found")
        else:
            logger.debug("No free slots available, skipping database poll")

    async def _database_reader(
        self,
        shutdown_event: asyncio.Event,
        worker_interval: float,
    ) -> None:
        """
        Database reader task that polls for pending work items and feeds them to the queue.

        Only fetches as many work items as there are free slots to ensure optimal
        distribution across horizontally scaled server instances.

        Args:
            shutdown_event: Event signaling shutdown
            worker_interval: Interval between database polls
        """
        while not shutdown_event.is_set():
            # Before each loop to fill the work queue, check if we need to resize first.
            # We want to resize _before_ we fill the work queue. This ensures that we
            # don't take workitems from the database w/o a Slot to immediately execute them.
            desired_slots = (await self.quotas()).get_max_parallel_work_items_in_process()
            if desired_slots != len(self.slot_manager.slots):
                # We would normally want this resize to be synchronous, but because we're
                # preventing the producer from adding more WorkItems to the queue, we can
                # be certain that Slots will not change from Idle->Executing while we're in
                # the critical resize section.
                await self._resize_slots(desired_slots, shutdown_event)

            try:
                await self._fetch_and_queue_work_items()
            except Exception as exc:
                logger.error(f"Error in database reader: {exc}", exc_info=exc)

            # Wait for the configured interval before next poll
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=worker_interval)
                # If we get here, shutdown was signaled
                break
            except TimeoutError:
                # Normal case: timeout expired, continue loop
                pass

        logger.info("Database reader shutting down")
