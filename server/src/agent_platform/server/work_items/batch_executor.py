"""
Batch Executor - Handles batch-based work item execution.

This module contains the BatchExecutor class which manages traditional
batch-based execution of work items, fetching and processing them in batches.
"""

import asyncio
import logging
from collections.abc import Sequence

from agent_platform.server.storage import StorageService
from agent_platform.server.work_items.executor import WorkItemExecutor

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "work-items"


class BatchExecutor:
    """
    Executor for batch-based work item processing.

    Batch mode fetches a batch of pending work items, executes them concurrently,
    and then fetches the next batch. This is the traditional execution mode.
    """

    def __init__(self, execute_work_item: WorkItemExecutor):
        """
        Initialize the BatchExecutor.

        Args:
            execute_work_item: Function that executes a work item
        """
        self.execute_work_item: WorkItemExecutor = execute_work_item

    async def run(self, shutdown_task: asyncio.Task) -> None:
        """
        Run the work items service in batch-based execution mode.

        Batch mode processes work items in batches, fetching a batch of pending items,
        executing them concurrently, and then fetching the next batch.

        Args:
            shutdown_task: The shutdown task to wait on between iterations
        """
        from agent_platform.server.shutdown_manager import ShutdownManager
        from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

        logger.info("Using batch-based execution mode")

        # Batch mode: traditional behavior
        while not ShutdownManager.should_worker_shutdown(WORKER_NAME):
            try:
                await self._worker_iteration()
            except Exception as exc:
                logger.error(f"Error processing work items: {exc}", exc_info=exc)

            await asyncio.wait([shutdown_task], timeout=WORK_ITEMS_SETTINGS.worker_interval)

    async def _worker_iteration(self) -> None:
        """
        Reads a batch of "PENDING" work_item rows from the database and
        marks them as "EXECUTING" and processes them as a batch.
        """
        from agent_platform.core.configurations.quotas import QuotasService

        quotas_service = await QuotasService.get_instance()
        max_batch_size = quotas_service.get_max_parallel_work_items_in_process()
        work_item_timeout = quotas_service.get_work_item_timeout_seconds()

        storage = StorageService.get_instance()
        work_item_ids = await storage.get_pending_work_item_ids(max_batch_size)

        if work_item_ids:
            logger.info(f"Found {len(work_item_ids)} work items to process. {work_item_ids!r}")
            logger.info(f"Dispatching work items {work_item_ids}")
            batch_results = await self.run_batch(work_item_ids, work_item_timeout)
            logger.info(f"Completed {len(batch_results)} work items concurrently")
        else:
            logger.debug("Found no work items to process.")

    async def run_batch(
        self,
        work_item_ids: Sequence[str],
        batch_timeout: float,
    ) -> Sequence[bool | BaseException]:
        """
        Execute a batch of work items concurrently.

        Args:
            work_item_ids: List of work item IDs to execute
            work_func: The function to execute for each work item
            batch_timeout: Maximum time to wait for all items to complete

        Returns:
            List of results (True/False/Exception) for each work item
        """
        storage = StorageService.get_instance()

        # Get all work items in a single query
        items = await storage.get_work_items_by_ids(list(work_item_ids))

        # Failed to find any work_items in the database to operate on.
        if not items:
            return []

        # Create tasks for each work item
        tasks = {}
        for item in items:
            logger.info(f"Dispatching work item (batch run) {item.work_item_id}")
            task: asyncio.Task[bool] = asyncio.create_task(self.execute_work_item(item))  # type: ignore[arg-type]
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

            # Wait for the cancelled tasks to return.
            await asyncio.gather(*pending, return_exceptions=True)

        for task, item in zip(tasks.values(), items, strict=True):
            if task in done:
                # Task completed before timeout - get its result
                try:
                    results.append(task.result())
                    logger.info(f"Work item {item.work_item_id} completed normally")
                except Exception as e:
                    results.append(e)
                    logger.warning(
                        f"Work item {item.work_item_id} failed with error: {e}", exc_info=e
                    )
            else:
                # Task didn't complete - mark as ERROR
                incomplete_work_item_ids.append(item.work_item_id)
                results.append(TimeoutError("Work item timeout exceeded"))
                logger.error(f"Work item {item.work_item_id} timed out, marking as ERROR")

        logger.info(f"Batch is complete {results!r}")

        # For all timed out work items which are still PENDING/EXECUTING,
        # mark them as having ERROR'ed.
        # We do this to prevent races between the task writing to the DB after we signaled
        # the cancellation
        if incomplete_work_item_ids:
            await storage.mark_incomplete_work_items_as_error(incomplete_work_item_ids)

        return results
