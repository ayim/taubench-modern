import asyncio
import hashlib
import hmac
import json
import logging
from urllib.parse import urljoin

import requests

from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemCallback,
    WorkItemCallbackPayload,
    WorkItemStatus,
)
from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB
from agent_platform.server.storage.option import StorageService
from agent_platform.server.work_items.settings import WORKSPACE_ID, get_workroom_url

logger = logging.getLogger(__name__)


class InvalidTimeoutError(PlatformError):
    """Raised when the timeout is not a positive number."""

    def __init__(self, message: str = "Callback timeout must be a positive number"):
        super().__init__(
            error_code=ErrorCode.UNPROCESSABLE_ENTITY,
            message=message,
        )


class InvalidWorkItemError(PlatformError):
    """Raised when the work item is invalid."""

    def __init__(self, message: str = "Work item is invalid"):
        super().__init__(
            error_code=ErrorCode.UNPROCESSABLE_ENTITY,
            message=message,
        )


async def execute_callbacks(work_item: WorkItem, status: WorkItemStatus, timeout: float = 60.0):
    """Execute all callbacks for a work item for the given status.

    Args:
        work_item: The work item to execute callbacks for.
        status: The status to execute callbacks for.
        timeout: The timeout in seconds for the callbacks to execute.
    """
    if timeout is None or timeout <= 0:
        raise InvalidTimeoutError()

    callbacks = [callback for callback in work_item.callbacks if callback.on_status == status]

    # No callbacks to execute
    if not callbacks:
        return

    async def _run_callbacks():
        async with asyncio.TaskGroup() as group:
            for callback in callbacks:
                group.create_task(_execute_callback(work_item, callback))

    try:
        await asyncio.wait_for(_run_callbacks(), timeout=timeout)
    except TimeoutError as _:
        logger.error(
            f"Callback execution for status {status} "
            f"timed out for work item {work_item.work_item_id}"
        )


def _build_work_item_url(work_item: WorkItem) -> str | None:
    """Build the work item URL."""
    pieces = {
        "workspace_id": WORKSPACE_ID,
        "agent_id": work_item.agent_id,
        "thread_id": work_item.thread_id,
    }
    # if the SEMA4AI_AGENT_SERVER_WORKROOM_URL env var is not set,
    # we shouldn't error out, return None instead.
    if workroom_url := get_workroom_url():
        for k, v in pieces.items():
            if v is None or not str(v).strip():
                raise InvalidWorkItemError(f"{k} should not be None or empty")

        url_parts = [str(v).strip() for v in pieces.values()]
        path = "/".join(url_parts)
        return urljoin(workroom_url, path)
    return None


async def _execute_callback(work_item: WorkItem, callback: WorkItemCallback):
    """Executes a single callback."""
    try:
        # Extract text content from thread messages
        text_messages = []
        for message in work_item.messages:
            for content in message.content:
                if isinstance(content, ThreadTextContent):
                    text_messages.append(content.text)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Sema4AI-WorkItems-Callback/1.0",
        }

        storage = StorageService.get_instance()
        # Get agent name as SYSTEM user
        system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)
        if work_item.agent_id is None:
            # at the time of callback, the agent_id has to be set.
            # if it isn't, we're in a bad state.
            raise InvalidWorkItemError(
                f"Agent ID is not set for work item {work_item.work_item_id} "
                "at the time of callback"
            )
        agent = await storage.get_agent(user_id=system_user.user_id, agent_id=work_item.agent_id)
        agent_name = agent.name

        work_item_url = _build_work_item_url(work_item)
        if work_item_url is None:
            logger.warning(
                f"Work item URL is not set for work item {work_item.work_item_id} "
                "at the time of callback"
            )
        # Coerce into our Payload type for strong type checking
        webhook_payload = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": work_item.work_item_id,
                "agent_id": work_item.agent_id,
                "thread_id": work_item.thread_id,
                "status": work_item.status.value,
                "work_item_url": work_item_url,
                "agent_name": agent_name,
            }
        )

        body = webhook_payload.model_dump()

        if callback.signature_secret:
            headers["X-SEMA4AI-SIGNATURE"] = _compute_signature(callback.signature_secret, body)

        logger.info(f"Sending callback for work item {work_item.work_item_id} to {callback.url}")
        logger.debug(f"Callback body: {body!r}")
        logger.debug(f"Callback headers: {headers!r}")

        response = requests.post(callback.url, json=body, headers=headers)
        response.raise_for_status()

        logger.info(f"Completed callback for work item {work_item.work_item_id} to {callback.url}")
    except Exception as e:
        # Don't re-raise the exception so other callbacks can continue
        logger.error(
            f"Callback failed for work item {work_item.work_item_id} to {callback.url}: {e}"
        )


def _compute_signature(secret: str, body: dict) -> str:
    """Computes a signature (SHA-256) for the body."""
    # Use sort_keys=True and separators for consistent JSON serialization
    body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode(), body_json.encode(), hashlib.sha256).hexdigest()
