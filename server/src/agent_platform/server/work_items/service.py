"""
Work Items Service - First-class service for managing work item execution.

This service encapsulates all business logic for work items processing, including:
- Running agents for work items
- Executing work items with validation
- Batch and slot-based execution modes
- Status management and callbacks
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Request

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.thread import Thread
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
)
from agent_platform.core.work_items.work_item import WorkItemStatusUpdatedBy
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "work-items"


class WorkItemsService:
    """
    Service for managing work item execution.

    This service provides all functionality needed to execute work items,
    including running agents, managing execution slots, batch processing,
    and status updates.
    """

    _instance: "WorkItemsService | None" = None

    def __init__(self):
        """Initialize the WorkItemsService."""
        self._work_func = self.run_agent

    @classmethod
    def get_instance(cls) -> "WorkItemsService":
        """Get the global WorkItemsService instance."""
        if cls._instance is None:
            cls._instance = WorkItemsService()
        return cls._instance

    async def run(
        self,
    ) -> None:
        """
        Start the work items processing loop.

        Dispatches to either batch-based or slot-based execution based on the
        execution_mode setting.

        Args:
            work_func: Function to execute for each work item. Defaults to self.run_agent.
        """
        from agent_platform.server.shutdown_manager import ShutdownManager
        from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

        shutdown_task = ShutdownManager.get_shutdown_task(WORKER_NAME)
        if shutdown_task is None:
            raise RuntimeError(f"Shutdown task not found for {WORKER_NAME} worker")

        logger.info("Using batch-based execution mode")
        # Batch mode: traditional behavior
        while not ShutdownManager.should_worker_shutdown(WORKER_NAME):
            try:
                await self._worker_iteration()
            except Exception as exc:
                logger.error(f"Error processing work items: {exc}", exc_info=exc)

            await asyncio.wait([shutdown_task], timeout=WORK_ITEMS_SETTINGS.worker_interval)

        logger.debug("finished work-items worker loop")

    async def _worker_iteration(
        self,
    ) -> None:
        """
        Reads a batch of "PENDING" work_item rows from the database and
        marks them as "EXECUTING" and processes them as a batch.
        """
        from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

        quotas_service = await QuotasService.get_instance()
        max_batch_size = quotas_service.get_max_parallel_work_items_in_process()

        work_item_ids = await self.get_pending_work_items(max_batch_size)

        if work_item_ids:
            logger.info(f"Found {len(work_item_ids)} work items to process. {work_item_ids!r}")
            logger.info(f"Dispatching work items {work_item_ids}")
            batch_results = await self.run_batch(
                work_item_ids, WORK_ITEMS_SETTINGS.work_item_timeout
            )
            logger.info(f"Completed {len(batch_results)} work items concurrently")
        else:
            logger.debug("Found no work items to process.")

    async def _get_system_user_id(self) -> str:
        """Get or create the system user for work items."""
        from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB
        from agent_platform.server.storage.errors import NoSystemUserError

        storage = StorageService.get_instance()
        try:
            return await storage.get_system_user_id()
        except NoSystemUserError:
            system_user, _ = await storage.get_or_create_user(
                sub=WORK_ITEMS_SYSTEM_USER_SUB,
            )
            logger.info(f"Created system user {system_user.user_id}")
            return system_user.user_id

    async def run_agent(self, item: WorkItem) -> bool:
        """
        Run an agent on the agent_server for a work item.

        Args:
            item: The work item to execute

        Returns:
            True if the agent completed successfully, False otherwise
        """
        from agent_platform.server.api.private_v2.runs import async_run, get_run_status
        from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB

        storage = StorageService.get_instance()
        # we know that this user exists already, so just get it
        system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)

        if not item.agent_id:
            logger.error(f"Work item {item.work_item_id}: Agent ID is required")
            return False

        # create a new thread for the work item
        thread = Thread(
            user_id=system_user.user_id,
            thread_id=str(uuid4()),
            agent_id=item.agent_id,
            name=item.get_thread_name(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            work_item_id=item.work_item_id,
        )
        await storage.upsert_thread(system_user.user_id, thread)

        # update the work item with the thread id and new file related messages
        item.thread_id = thread.thread_id
        await storage.update_work_item(item)

        # Next: build up the user-messages in the thread. The work_item will already have
        # `messages` filled out now. We need to add in corresponding messages for each file.
        files = await storage.get_workitem_files(
            work_item_id=item.work_item_id,
            user_id=system_user.user_id,
        )
        for file in files:
            # TODO maybe add bulk method to do all associations at once?
            # Don't create new file_ids while we associate these files with the work item.
            await storage.associate_work_item_file(
                file_id=file.file_id,
                work_item=item,
                agent_id=item.agent_id,
                thread_id=item.thread_id,
            )

            file_upload_message = ThreadMessage(
                role="user",
                content=[
                    # This needs to be aligned with how we expect our clients
                    # to handle files (which is to upload and then insert a ThreadAttachmentContent
                    # into the thread with the appropriate metadata from the file)
                    # See workroom/spar-ui/src/queries/threads.ts as reference
                    ThreadAttachmentContent(
                        name=file.file_ref,
                        mime_type=file.mime_type,
                        uri=f"agent-server-file://{file.file_id}",
                    ),
                ],
            )

            item.messages.append(file_upload_message)

        payload = item.to_initiate_stream_payload()
        logger.info(
            f"Work item {item.work_item_id}: Invoking agent "
            f"{item.agent_id} with messages {payload.messages}"
        )
        invoke_resp = await async_run(
            item.agent_id,
            payload,
            user=system_user,
            storage=storage,
            request=Request(scope={"type": "http", "method": "POST"}),
        )
        run_id = invoke_resp.run_id
        logger.info(f"Work item {item.work_item_id}: Run {run_id} started")

        # Poll for the run status until it is completed or failed
        while True:
            run_status_resp = await get_run_status(run_id, user=system_user, storage=storage)
            if not run_status_resp:
                logger.warning(f"Run status not found for run {run_id}")
                await asyncio.sleep(1)
                continue

            if run_status_resp.is_success:
                # Update messages with the thread's results?
                await storage.update_work_item_from_thread(
                    system_user.user_id,
                    item.work_item_id,
                    run_status_resp.thread_id,
                )

                logger.info(f"Work item {item.work_item_id}: Run {run_id} completed successfully")

                return True
            elif run_status_resp.is_failure:
                logger.error(f"Work item {item.work_item_id}: Run {run_id} failed")
                return False
            else:
                logger.debug(
                    f"Work item {item.work_item_id}: Run {run_id} is {run_status_resp.status}"
                )
                await asyncio.sleep(1)

    async def execute_work_item(
        self,
        item: WorkItem,
        agent_func: Callable[[WorkItem], Awaitable[bool]],
    ) -> bool:
        """
        Execute a single work item with validation and status updates.

        Args:
            item: The work item to execute
            agent_func: The function to execute the agent (typically self.run_agent)

        Returns:
            True if the work item was executed successfully, False otherwise
        """
        from agent_platform.server.work_items.callbacks import execute_callbacks
        from agent_platform.server.work_items.judge import _validate_success

        storage = StorageService.get_instance()
        system_user_id = await self._get_system_user_id()

        try:
            logger.info(f"Starting execution on work item {item.work_item_id}")

            result = await agent_func(item)

            try:
                item = await storage.get_work_item(item.work_item_id)
                current_status = item.status
            except Exception:  # If fetch fails, fall back to our computed status
                logger.error("Error fetching work item %s, validating anyway", item.work_item_id)
                current_status = WorkItemStatus.EXECUTING

            # Only run judge if the work item status wasn't already set by user or runbook step
            if current_status == WorkItemStatus.EXECUTING:
                logger.info(
                    "Completed execution on work item %s, function result: %s (updating status)",
                    item.work_item_id,
                    result,
                )

                new_status = (await _validate_success(item)) if result else WorkItemStatus.ERROR

                if new_status == WorkItemStatus.COMPLETED:
                    await storage.complete_work_item(
                        system_user_id, item.work_item_id, WorkItemCompletedBy.AGENT
                    )
                else:
                    await storage.update_work_item_status(
                        system_user_id,
                        item.work_item_id,
                        new_status,
                        WorkItemStatusUpdatedBy.AGENT,
                    )
                item.status = new_status

                logger.info(
                    "Completed validation of work item %s, final status: %s",
                    item.work_item_id,
                    new_status,
                )
                # Will be "COMPLETED", "NEEDS_REVIEW", or "ERROR"
                await execute_callbacks(item, new_status)
            else:
                logger.info(
                    "Work item %s is in already in status %s, skipping validation",
                    item.work_item_id,
                    item.status,
                )
                await execute_callbacks(item, item.status)

            return result
        except Exception as e:
            logger.error(f"Error executing work item {item.work_item_id}: {e}", exc_info=e)

            await storage.update_work_item_status(
                system_user_id,
                item.work_item_id,
                WorkItemStatus.ERROR,
                WorkItemStatusUpdatedBy.SYSTEM,
            )

            return False

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
            task = asyncio.create_task(self.execute_work_item(item, self._work_func))
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
                    logger.warning(
                        f"Work item {item.work_item_id} failed with error: {e}", exc_info=e
                    )
            else:
                # Task didn't complete - mark as ERROR
                incomplete_work_item_ids.append(item.work_item_id)
                results.append(TimeoutError("Work item timeout exceeded"))
                logger.error(f"Work item {item.work_item_id} timed out, marking as ERROR")

        # For all timed out work items which are still PENDING/EXECUTING,
        # mark them as having ERROR'ed.
        # We do this to prevent races between the task writing to the DB after we signaled
        # the cancellation
        if incomplete_work_item_ids:
            await storage.mark_incomplete_work_items_as_error(incomplete_work_item_ids)

        return results

    async def get_pending_work_items(self, limit: int) -> Sequence[str]:
        """
        Get pending work item IDs from storage.

        Args:
            limit: Maximum number of work item IDs to retrieve

        Returns:
            List of work item IDs
        """
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()
        return await storage.get_pending_work_item_ids(limit)
