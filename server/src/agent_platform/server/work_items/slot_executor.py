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
from typing import Literal

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage import BaseStorage, StorageService
from agent_platform.server.work_items.executor import WorkItemExecutor

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "work-items"


@dataclass
class SlotState:
    """State tracking for a single execution slot."""

    slot_id: int
    status: Literal["idle", "executing"] = "idle"
    work_item_id: str | None = None
    task: asyncio.Task | None = None
    crash_count: int = 0


@dataclass
class SlotManager:
    """Manages the state of all execution slots."""

    slots: dict[int, SlotState] = field(default_factory=dict)

    def get_num_free_slots(self) -> int:
        """Return the number of slots that are currently idle."""
        return sum(1 for slot in self.slots.values() if slot.status == "idle")

    def get_slot_status(self) -> list[dict]:
        """Return current status of all slots for internal API."""
        return [
            {
                "slot_id": slot.slot_id,
                "status": slot.status,
                "work_item_id": slot.work_item_id,
            }
            for slot in self.slots.values()
        ]


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

    async def quotas(self) -> QuotasService:
        """Get the QuotasService instance."""
        if self._quotas is None:
            self._quotas = await QuotasService.get_instance()
        return self._quotas

    def get_slot_status(self) -> list[dict]:
        """
        Get the current status of all execution slots.

        Returns:
            List of slot status dictionaries if slot-based mode is active, None otherwise.
            Each dict contains: slot_id, status ("idle" or "executing"), and work_item_id.
        """
        return self.slot_manager.get_slot_status()

    def _get_slot_tasks(self) -> list[tuple[asyncio.Task, int]]:
        """
        Get all active slot tasks and their corresponding slot IDs.

        Returns:
            List of (task, slot_id) tuples for slots that have an active task.
        """
        result = []
        for slot_id, slot_state in self.slot_manager.slots.items():
            if slot_state.task is not None:
                result.append((slot_state.task, slot_id))
        return result

    def _find_slot_id_for_task(self, task: asyncio.Task) -> int | None:
        """
        Find the slot ID for a given task.

        Args:
            task: The task to find the slot ID for

        Returns:
            The slot ID if found, None otherwise
        """
        for slot_id, slot_state in self.slot_manager.slots.items():
            if slot_state.task == task:
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
        from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

        task = asyncio.create_task(
            self._slot_executor_task(
                slot_id,
                executor_shutdown_event,
                WORK_ITEMS_SETTINGS.work_item_timeout,
            )
        )
        task.set_name(f"work-items-slot-{slot_id}")
        self.slot_manager.slots[slot_id].task = task
        return task

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
        slot_state.task = None

        # We never call .cancel() on the Slot task, so the only possible way
        # for it to complete is for an uncaught Exception to be raised.
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
        for i in range(num_slots):
            self.slot_manager.slots[i] = SlotState(slot_id=i)

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

        # Main execution loop: wait for shutdown or handle task crashes
        try:
            while True:
                # TODO add slot resizing logic here.

                slot_tasks = [task for task, _ in self._get_slot_tasks()]
                all_tasks = [global_shutdown_task, self.reader_task, *slot_tasks]
                done, _ = await asyncio.wait(
                    all_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Check if shutdown was requested
                if global_shutdown_task in done:
                    logger.info("Shutdown requested, stopping slot-based execution")
                    break

                # Handle crashed tasks - restart them individually
                for task in done:
                    if task == self.reader_task:
                        self.reader_task = self._handle_reader_crash(task, executor_shutdown_event)
                    else:
                        maybe_slot_id = self._find_slot_id_for_task(task)
                        if maybe_slot_id is not None:
                            self._handle_slot_crash(task, maybe_slot_id, executor_shutdown_event)
                        else:
                            # Unknown task (shouldn't happen)
                            logger.error(f"Unknown task completed: {task.get_name()}")

        finally:
            # Signal shutdown to all worker tasks
            executor_shutdown_event.set()

            # Gracefully shutdown all worker tasks
            slot_tasks = [task for task, _ in self._get_slot_tasks()]
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

            # Cancel all of the internal tasks.
            for task in tasks_to_wait:
                if not task.done():
                    task.cancel()

            # Give the tasks a few seconds to clean up before we return.
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=5.0,
                )
            except TimeoutError:
                logger.error("Work Items background tasks are still running after cancellation.")
                # if they _still_ haven't clean up, we're just giving up.

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

        This method handles the complete lifecycle of executing one work item:
        - Mark slot as executing
        - Execute the work item with timeout
        - Handle timeout and errors
        - Mark slot as idle

        Args:
            item: The work item to execute
            slot_state: The slot state to update
            work_item_timeout: Timeout for the work item execution
        """
        slot_id = slot_state.slot_id

        # Mark slot as executing
        slot_state.status = "executing"
        slot_state.work_item_id = item.work_item_id

        logger.info(f"Slot {slot_id} executing work item {item.work_item_id}")

        try:
            # Create the execution task and store it for potential cancellation
            # Note: execute_work_item is typed as Awaitable but returns a Coroutine at runtime
            slot_state.task = asyncio.create_task(self.execute_work_item(item))  # type: ignore[arg-type]

            await asyncio.wait_for(slot_state.task, timeout=work_item_timeout)

            logger.info(f"Slot {slot_id} completed work item {item.work_item_id} successfully")

        except TimeoutError:
            # Work item timed out
            logger.error(
                f"Slot {slot_id} work item {item.work_item_id} timed out after "
                f"{work_item_timeout}s, marking as ERROR"
            )

            # Cancel the task
            if slot_state.task and not slot_state.task.done():
                slot_state.task.cancel()
                with suppress(asyncio.CancelledError):
                    await slot_state.task

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
            slot_state.task = None

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

    async def _slot_executor_task(  # noqa: C901, PLR0912
        self,
        slot_id: int,
        shutdown_event: asyncio.Event,
        work_item_timeout: float,
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

        logger.info(f"Work Items Slot Executor {slot_id} started")

        while not shutdown_event.is_set():
            inner_tasks = []
            try:
                # Wait for work item from queue or shutdown signal
                # Use wait() to allow shutdown to interrupt the queue wait
                get_task = asyncio.create_task(self._work_queue.get())
                inner_tasks.append(get_task)
                shutdown_task = asyncio.create_task(shutdown_event.wait())
                inner_tasks.append(shutdown_task)

                done, pending = await asyncio.wait(inner_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Cancel pending tasks and wait for them all to complete
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)  # type: ignore[reportUnknownReturnType]
                # Our inner tasks are done, no need for another await.
                inner_tasks.clear()

                # Check if shutdown was signaled
                if shutdown_event.is_set():
                    # If we got an item, put it back
                    if get_task in done and not get_task.cancelled():
                        try:
                            item = get_task.result()
                            await self._return_work_item_to_pool_on_shutdown(item, slot_id)
                        except Exception as exc:
                            logger.error(
                                f"Slot {slot_id} error picking up item: {exc}", exc_info=exc
                            )
                    break

                # Pick the item off the queue
                item = get_task.result()
                if item is None:
                    raise ValueError("Did not get a work item from the queue, should not happen")

                # Actually run the work item!
                await self._execute_work_item_in_slot(item, slot_state, work_item_timeout)

            except asyncio.CancelledError:
                # If we get here, the outer loop has called cancel() on us.
                logger.info(f"Slot {slot_id} cancelled, shutting down ({slot_state.work_item_id})")

                # We got caught in the polling for an new item.
                if inner_tasks:
                    for task in inner_tasks:
                        if not task.done():
                            task.cancel()
                    if inner_tasks:
                        await asyncio.gather(*inner_tasks, return_exceptions=True)  # type: ignore[reportUnknownReturnType]

                # Or, we were cancelled in the work item execution.
                if slot_state.task and not slot_state.task.done():
                    slot_state.task.cancel()
                    with suppress(asyncio.CancelledError):
                        await slot_state.task

                # Mark as error in database if it's still in PENDING/EXECUTING state
                if slot_state.work_item_id:
                    await self._storage.mark_incomplete_work_items_as_error(
                        [slot_state.work_item_id]
                    )

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
                slot_state.task = None

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
