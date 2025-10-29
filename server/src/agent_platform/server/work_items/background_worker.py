import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from textwrap import dedent
from typing import assert_never, cast
from uuid import uuid4

from fastapi import Request

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.context import AgentServerContext
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.thread import Thread
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
)
from agent_platform.core.work_items.work_item import WorkItemStatusUpdatedBy
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.runs import (
    async_run,
    get_run_status,
)
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB
from agent_platform.server.shutdown_manager import ShutdownManager
from agent_platform.server.storage import StorageService
from agent_platform.server.storage.errors import NoSystemUserError
from agent_platform.server.work_items.callbacks import execute_callbacks
from agent_platform.server.work_items.settings import WORK_ITEMS_SETTINGS

logger = logging.getLogger(__name__)

# Worker name constant for shutdown manager
WORKER_NAME = "work_items"


def _load_judge_prompt() -> str:
    """Load the judge prompt from the bundled resources.

    Uses importlib.resources for development and sys._MEIPASS for PyInstaller
    bundled environments.

    Returns:
        The judge prompt content as a string.
    """
    import sys
    from pathlib import Path

    from agent_platform.server.constants import IS_FROZEN

    if IS_FROZEN:
        # PyInstaller bundle - use sys._MEIPASS
        base_path = Path(getattr(sys, "_MEIPASS"))  # noqa: B009
        judge_prompt_path = (
            base_path / "agent_platform" / "server" / "work_items" / "judge_prompt.txt"
        )
        content = judge_prompt_path.read_text(encoding="utf-8")
    else:
        # Development environment - use importlib.resources
        from importlib import resources

        package_resources = resources.files("agent_platform.server.work_items")
        judge_prompt_resource = package_resources / "judge_prompt.txt"
        content = judge_prompt_resource.read_text(encoding="utf-8")

    return dedent(content)


async def _validate_success(item: WorkItem) -> WorkItemStatus:
    # 1. System message describing the judge's role
    system_message = dedent("""
        You are an expert evaluator of LLM conversations. Your role is to assess whether \
        an AI agent successfully completed the task given to it by the user by analyzing the \
        conversation history between the agent and user. The AI Agent is responsible for \
        using data, tools and other resources to accomplish a business task
        which a human would have previously done. Agents often have tools to verify that
        they have completed the task successfully -- when these tasks fail (including reasons
        where the business logic verification fails), this means that the agent has failed
        to complete the task successfully.
    """)

    # 2-5. Combined judgment prompt with criteria, primer, messages, and final instructions
    judge_prompt_msg = _load_judge_prompt()

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
    # TODO: using the message conversion for the default arch, but work items
    # could have it's _own_ conversion tailored to the judgement task
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )
    converted_messages = await kernel.converters.thread_messages_to_prompt_messages(item.messages)
    # Format the conversation thread through a temporary prompt instance
    temp_prompt = Prompt(messages=cast(list, converted_messages))
    formatted_conversation_thread = temp_prompt.to_pretty_yaml(include=["messages"])
    judge_prompt_msg = judge_prompt_msg.format(conversation_thread=formatted_conversation_thread)

    prompt = Prompt(
        system_instruction=system_message,
        messages=[PromptUserMessage(content=[PromptTextContent(text=judge_prompt_msg)])],
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
            response_text = text_content[-1]
            logger.debug(f"Work item validation response: {response_text}")

            # Extract the classification from the structured response
            for line in response_text.split("\n"):
                clean_line = line.strip()
                if clean_line.startswith("CLASSIFICATION:"):
                    classification = clean_line.split("CLASSIFICATION:", 1)[1].strip()
                    try:
                        return WorkItemStatus(classification)
                    except ValueError:
                        logger.warning(
                            f"Work item validation failed: invalid classification: {classification}"
                        )
                        break

            # Fallback: try to parse the entire response as before (for backward compatibility)
            try:
                return WorkItemStatus(response_text.strip())
            except ValueError:
                logger.warning(
                    f"Work item validation failed: could not parse response: {response_text!r}"
                )
                pass
    # If we get here, the work item validation failed; return INDETERMINATE
    return WorkItemStatus.INDETERMINATE


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
            logger.debug(f"Work item {item.work_item_id}: Run {run_id} is {run_status_resp.status}")
            await asyncio.sleep(1)

    assert_never(run_agent)


async def worker_loop(
    work_func: Callable[[WorkItem], Awaitable[bool]] = run_agent,
) -> None:
    """
    Runs a loop which processes work items, sleeping the configured amount between iterations.
    """
    shutdown_task = ShutdownManager.get_shutdown_task(WORKER_NAME)
    if shutdown_task is None:
        raise RuntimeError(f"Shutdown task not found for {WORKER_NAME} worker")

    while not ShutdownManager.should_worker_shutdown(WORKER_NAME):
        try:
            await worker_iteration(work_func)
        except Exception as exc:
            logger.error(f"Error processing work items: {exc}", exc_info=exc)

        await asyncio.wait([shutdown_task], timeout=WORK_ITEMS_SETTINGS.worker_interval)

    logger.debug("finished work-items worker loop")


async def worker_iteration(
    work_func: Callable[[WorkItem], Awaitable[bool]],
) -> None:
    """
    Reads a batch of "PENDING" work_item rows from the database and
    marks them as "EXECUTING" and processes them as a batch.
    """
    storage = StorageService.get_instance()

    quotas_service = await QuotasService.get_instance()
    max_batch_size = quotas_service.get_max_parallel_work_items_in_process()

    work_item_ids = await storage.get_pending_work_item_ids(max_batch_size)

    if work_item_ids:
        logger.info(f"Found {len(work_item_ids)} work items to process. {work_item_ids!r}")
        logger.info(f"Dispatching work items {work_item_ids}")
        batch_results = await run_batch(
            work_item_ids, work_func, WORK_ITEMS_SETTINGS.work_item_timeout
        )
        logger.info(f"Completed {len(batch_results)} work items concurrently")
    else:
        logger.debug("Found no work items to process.")


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

    # For all timed out work items which are still PENDING/EXECUTING,
    # mark them as having ERROR'ed.
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
