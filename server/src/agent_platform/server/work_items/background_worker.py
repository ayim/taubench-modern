import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import assert_never
from uuid import uuid4

from fastapi import Request

from agent_platform.core.context import AgentServerContext
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.thread import ThreadTextContent
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.runs import (
    async_run,
    get_run_status,
)
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.storage import StorageService
from agent_platform.server.storage.errors import NoSystemUserError
from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

logger = logging.getLogger(__name__)

WORK_ITEMS_SYSTEM_USER_SUB = "tenant:work-items:system:system_user"


async def _validate_success(item: WorkItem) -> WorkItemStatus:
    system_message = (
        "You are a helpful agent that validates if the work item executed by an AI "
        "agent was completed successfully. \n"
        "Review the conversation history and determine if the task was completed "
        "successfully. \n\n"
        "Assessment criteria: \n"
        "1. Task completion: Check if the original request or work item was fully "
        "addressed \n"
        "2. Tool usage effectiveness: Evaluate if the agent used available tools "
        "appropriately to accomplish the task \n"
        "3. Error handling: Verify that any errors were properly addressed or "
        "resolved \n"
        "4. Analysis quality: Ensure the agent provided thorough analysis and "
        "insights when required \n"
        "5. User satisfaction: Consider if the response adequately addresses the "
        "user's needs \n"
        "6. Completeness: Ensure no important aspects of the task were left "
        "unfinished \n\n"
        "Signs of successful completion: \n"
        "- The agent provided a complete solution to the requested task \n"
        "- Available tools were used effectively to gather information or perform "
        "actions \n"
        "- All requirements were met or exceeded \n"
        "- The agent confirmed successful completion \n"
        "- Analysis was thorough and accurate \n"
        "- The agent successfully navigated through any challenges encountered \n\n"
        "Signs requiring human review: \n"
        "- The agent encountered unresolved errors or exceptions \n"
        "- The solution is incomplete or partially implemented \n"
        "- The agent expressed uncertainty about the correctness of the solution \n"
        "- Tools failed to execute properly or returned unexpected results \n"
        "- The agent requested human intervention or clarification \n"
        "- The agent stated it cannot complete the task due to missing tools or capabilities \n"
        "- The agent identified contradictory or ambiguous instructions requiring clarification \n"
        "- Complex business logic or critical systems were analyzed without proper "
        "validation \n"
        "- The conversation ended abruptly without clear completion \n"
        "- The agent was unable to access required tools or information \n\n"
        "You must respond with ONLY one of these two values: \n"
        f"{WorkItemStatus.COMPLETED.value} - if the work item was successfully "
        "completed based on the criteria above \n"
        f"{WorkItemStatus.NEEDS_REVIEW.value} - if the work item requires human "
        "review or was not completed successfully\n"
    )

    storage = StorageService.get_instance()
    user = await storage.get_user_by_id(item.user_id)

    # Create a minimal kernel context to access the converters interface
    mock_request = Request(scope={"type": "http", "method": "POST"})
    ctx = AgentServerContext.from_request(
        request=mock_request,
        user=user,
        version="2.0.0",
    )
    kernel = create_minimal_kernel(ctx)

    # Use the existing thread-to-prompt message converter
    converted_messages = await kernel.converters.thread_messages_to_prompt_messages(item.messages)

    # Convert to the expected message types
    prompt_messages = []
    for msg in converted_messages:
        prompt_messages.append(msg)

    prompt = Prompt(
        system_instruction=system_message,
        messages=prompt_messages,
        temperature=0.0,
    )
    result = await prompt_generate(
        prompt,
        user=user,
        storage=storage,
        request=Request(scope={"type": "http", "method": "POST"}),
        agent_id=item.agent_id,
    )
    if content := result.content:
        if text_content := [c.text for c in content if isinstance(c, ResponseTextContent)]:
            try:
                logger.debug(f"Work item validation response: {text_content[-1]}")
                return WorkItemStatus(text_content[-1])
            except ValueError:
                logger.warning(f"Work item validation failed: invalid response: {content!r}")
                pass
    # If we get here, the work item validation failed; return NEEDS_REVIEW
    return WorkItemStatus.NEEDS_REVIEW


async def run_agent(item: WorkItem) -> bool:
    """
    Run an agent on the agent_server.
    """
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
        name=f"Work Item {item.work_item_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(system_user.user_id, thread)

    # update the work item with the thread id and new file related messages
    item.thread_id = thread.thread_id
    await storage.update_work_item(item)

    # copy all work item files to the thread, but don't create new file_id's in the process.
    files = await storage.get_workitem_files(
        work_item_id=item.work_item_id,
        user_id=system_user.user_id,
    )
    for file in files:
        # TODO maybe add bulk method to do all associations at once?
        await storage.associate_work_item_file(
            file_id=file.file_id,
            work_item=item,
            agent_id=item.agent_id,
            thread_id=item.thread_id,
        )

        file_upload_message = ThreadMessage(
            role="user",
            content=[
                ThreadTextContent(
                    text=f"Uploaded [{file.file_ref}]({file.file_url})",
                )
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
            logger.info(f"Work item {item.work_item_id}: Run {run_id} is {run_status_resp.status}")
            await asyncio.sleep(1)

    assert_never(run_agent)


async def worker_loop(
    shutdown_event: asyncio.Event,
    work_func: Callable[[WorkItem], Awaitable[bool]],
) -> None:
    """
    Runs a loop which processes work items, sleeping the configured amount between iterations.
    """
    while not shutdown_event.is_set():
        logger.info("searching for work items to process")
        try:
            await worker_iteration(work_func)
        except Exception as exc:
            logger.error(f"Error processing work items: {exc}", exc_info=exc)

        await asyncio.sleep(WORK_ITEMS_SETTINGS.worker_interval)

    logger.info("finished work-items worker loop")


async def worker_iteration(
    work_func: Callable[[WorkItem], Awaitable[bool]],
) -> None:
    """
    Reads a batch of "PENDING" work_item rows from the database and
    marks them as "EXECUTING" and processes them as a batch.
    """
    storage = StorageService.get_instance()

    work_item_ids = await storage.get_pending_work_item_ids(WORK_ITEMS_SETTINGS.max_batch_size)

    logger.info(f"Found {len(work_item_ids)} work items to process. {work_item_ids!r}")

    if work_item_ids:
        logger.info(f"Dispatching work items {work_item_ids}")
        batch_results = await run_batch(
            work_item_ids, work_func, WORK_ITEMS_SETTINGS.work_item_timeout
        )
        logger.info(f"Completed {len(batch_results)} work items concurrently")


async def run_batch(
    work_item_ids: Sequence[str],
    work_func: Callable[[WorkItem], Awaitable[bool]],
    batch_timeout: float,
) -> Sequence[bool | BaseException]:
    """
    Given a list of work_item_ids, fetch the full work_item objects, and
    execute a task to run each. Wait for completion over all tasks.
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
        task = asyncio.create_task(execute_work_item(item, work_func))
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
                logger.warning(f"Work item {item.work_item_id} failed with error: {e}", exc_info=e)
        else:
            # Task didn't complete - mark as ERROR
            incomplete_work_item_ids.append(item.work_item_id)
            results.append(TimeoutError("Work item timeout exceeded"))
            logger.error(f"Work item {item.work_item_id} timed out, marking as ERROR")

    # For all timed out work items which are still PENDING/EXECUTING, mark them as having ERROR'ed.
    # We do this to prevent races between the task writing to the DB after we signaled
    # the cancellation
    if incomplete_work_item_ids:
        await storage.mark_incomplete_work_items_as_error(incomplete_work_item_ids)

    return results


async def execute_work_item(
    item: WorkItem,
    agent_func: Callable[[WorkItem], Awaitable[bool]],
) -> bool:
    """
    Call agent server to process one work item and update the database with the
    result.

    Args:
        item: The work item to execute.
        agent_client: The agent client.
        agent_func: The function to execute the agent.

    Returns:
        True if the work item was executed successfully, False otherwise.
    """
    storage = StorageService.get_instance()

    try:
        system_user_id = await storage.get_system_user_id()
    except NoSystemUserError:
        system_user, _ = await storage.get_or_create_user(
            sub=WORK_ITEMS_SYSTEM_USER_SUB,
        )
        logger.info(f"Created system user {system_user.user_id}")
        system_user_id = system_user.user_id

    try:
        logger.info(f"Starting execution on work item {item.work_item_id}")

        result = await agent_func(item)

        # Do not overwrite CANCELLED if the user cancelled while we were executing.
        try:
            latest_item = await storage.get_work_item(item.work_item_id)
            current_status = latest_item.status
        except Exception:  # If fetch fails, fall back to our computed status
            current_status = None
            latest_item = item

        # Only update if the current status is not CANCELLED
        if current_status != WorkItemStatus.CANCELLED:
            logger.info(
                "Completed execution on work item %s, result: %s (updating status)",
                item.work_item_id,
                result,
            )

            new_status = (await _validate_success(latest_item)) if result else WorkItemStatus.ERROR

            await storage.update_work_item_status(system_user_id, item.work_item_id, new_status)
        else:
            logger.info(
                "Work item %s was cancelled during execution: leaving status as CANCELLED",
                item.work_item_id,
            )

        return result
    except Exception as e:
        logger.error(f"Error executing work item {item.work_item_id}: {e}", exc_info=e)

        await storage.update_work_item_status(
            system_user_id,
            item.work_item_id,
            WorkItemStatus.ERROR,
        )

        return False
