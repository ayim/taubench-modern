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
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import Request

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.thread import Thread
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
)
from agent_platform.core.work_items.work_item import WorkItemStatusUpdatedBy, WorkItemTaskStatus
from agent_platform.server.log_config import get_work_items_transaction_logger
from agent_platform.server.storage import StorageService
from agent_platform.server.work_items.batch_executor import BatchExecutor
from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS
from agent_platform.server.work_items.slot_executor import SlotExecutor

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

    def __init__(self, execution_mode: Literal["batch", "slots"]):
        """Initialize the WorkItemsService."""
        self._executor = (
            SlotExecutor(self.execute_work_item) if execution_mode == "slots" else BatchExecutor(self.execute_work_item)
        )

        if WORK_ITEMS_SETTINGS.enable_transaction_log:
            self._transaction_logger = get_work_items_transaction_logger()
        else:
            from sema4ai.common.null import NULL

            self._transaction_logger = NULL

    @classmethod
    def get_instance(cls) -> "WorkItemsService":
        """Get the global WorkItemsService instance."""
        if cls._instance is None:
            from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

            # TODO move proper into configuration/quotas service.
            execution_mode = WORK_ITEMS_SETTINGS.execution_mode
            if execution_mode not in ["batch", "slots"]:
                raise ValueError(f"Invalid execution mode: {execution_mode}")
            cls._instance = WorkItemsService(execution_mode)  # type: ignore[arg-type]
        return cls._instance

    def get_slot_status(self) -> list[WorkItemTaskStatus] | None:
        """
        Get the current status of all execution slots.

        Returns:
            List of task statuses if the Executor mode supports reporting status, else None.
        """
        if self._executor is None or not isinstance(self._executor, SlotExecutor):
            return None
        return self._executor.get_slot_status()

    async def cancel_work_item_execution(self, work_item_id: str) -> bool:
        """Attempt to cancel a work item that is currently executing.

        Returns True if the executor confirmed the work item was found and cancellation was
        initiated. Returns False if the executor is not slot-based or the work item was not
        associated with any active slot.
        """
        if self._executor is None or not isinstance(self._executor, SlotExecutor):
            logger.warning("Work item %s is executing but no slot-based executor is available", work_item_id)
            return False

        return await self._executor.cancel_work_item(work_item_id)

    async def run(
        self,
    ) -> None:
        """
        Start the work items processing loop.

        Dispatches to either batch-based or slot-based execution based on the
        execution_mode setting.
        """
        from agent_platform.server.shutdown_manager import ShutdownManager

        shutdown_task = ShutdownManager.get_shutdown_task(WORKER_NAME)
        if shutdown_task is None:
            raise RuntimeError(f"Shutdown task not found for {WORKER_NAME} worker")

        await self._executor.run(shutdown_task)

        logger.debug("finished work-items worker loop")

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
                    # See workroom/frontend/src/queries/threads.ts as reference
                    ThreadAttachmentContent(
                        name=file.file_ref,
                        mime_type=file.mime_type,
                        uri=f"agent-server-file://{file.file_id}",
                    ),
                ],
            )

            item.messages.append(file_upload_message)

        payload = item.to_initiate_stream_payload()
        logger.info(f"Work item {item.work_item_id}: Invoking agent {item.agent_id} with messages {payload.messages}")
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
                logger.debug(f"Work item {item.work_item_id}: Run {run_id} is {run_status_resp.status}")
                await asyncio.sleep(1)

    async def execute_work_item(
        self,
        item: WorkItem,
    ) -> bool:
        """
        Execute a single work item, runs the Judge, and invokes any callbacks. This method
        updates the status in the database as execution progresses.

        Args:
            item: The work item to execute

        Returns:
            True if the work item was executed successfully, False otherwise
        """
        from agent_platform.server.work_items.callbacks import execute_callbacks
        from agent_platform.server.work_items.judge import _validate_success

        storage = StorageService.get_instance()
        system_user_id = await self._get_system_user_id()

        # Get transaction logger with work_item_id bound for context
        txn_logger = self._transaction_logger.bind(work_item_id=item.work_item_id)

        try:
            logger.info(f"Starting execution on work item {item.work_item_id}")

            # Transaction log: work item started
            txn_logger.info(
                None,
                event_type="work_item_started",
                status=item.status.value if item.status else None,
            )

            # Run the WorkItem through the LLM.
            result = await self.run_agent(item)

            # Transaction log: agent completed
            txn_logger.info(
                None,
                event_type="agent_completed",
                result=result,
            )

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

                # Transaction log: judge started
                txn_logger.info(
                    None,
                    event_type="judge_started",
                    agent_result=result,
                )

                new_status = (await _validate_success(item)) if result else WorkItemStatus.ERROR

                # Transaction log: judge completed
                txn_logger.info(
                    None,
                    event_type="judge_completed",
                    judge_result=new_status.value,
                )

                # Judge could have taken some time, check again.
                # TODO needs a test
                item = await storage.get_work_item(item.work_item_id)
                current_status = item.status
                if current_status != WorkItemStatus.EXECUTING:
                    logger.warning(
                        "Work item %s is no longer EXECUTING, skipping final status update",
                        item.work_item_id,
                    )
                    return result

                if new_status == WorkItemStatus.COMPLETED:
                    await storage.complete_work_item(system_user_id, item.work_item_id, WorkItemCompletedBy.AGENT)
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

                # Transaction log: judge skipped
                txn_logger.info(
                    None,
                    event_type="judge_skipped",
                    current_status=item.status.value,
                    reason="status_already_set",
                )

                await execute_callbacks(item, item.status)

            # Transaction log: work item finished (success path)
            txn_logger.info(
                None,
                event_type="work_item_finished",
                final_status=item.status.value,
                result=result,
            )

            return result
        except asyncio.CancelledError:
            logger.info("Execution of work item %s was cancelled", item.work_item_id)
            # Propagate cancellation so the slot executor can clean up gracefully
            raise
        except Exception as e:
            logger.error(f"Error executing work item {item.work_item_id}: {e}", exc_info=e)

            await storage.update_work_item_status(
                system_user_id,
                item.work_item_id,
                WorkItemStatus.ERROR,
                WorkItemStatusUpdatedBy.SYSTEM,
            )

            # Transaction log: work item finished (error path)
            txn_logger.error(
                None,
                event_type="work_item_finished",
                final_status=WorkItemStatus.ERROR.value,
                result=False,
                error=str(e),
            )

            return False
