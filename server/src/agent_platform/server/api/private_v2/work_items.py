from http import HTTPStatus
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from structlog import get_logger

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.payloads.create_work_item import (
    CreateWorkItemPayload,
)
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.work_items.work_item import WorkItem, WorkItemCallback, WorkItemStatus
from agent_platform.server.api.dependencies import FileManagerDependency, StorageDependency
from agent_platform.server.auth import AuthedUser
from agent_platform.server.constants import SystemConfig
from agent_platform.server.work_items.settings import WORK_ITEMS_SYSTEM_USER_SUB


def _require_workitems_enabled():
    """Raise an error if work items are disabled in configuration."""
    if not SystemConfig.enable_workitems:
        raise PlatformHTTPError(ErrorCode.FORBIDDEN, "Work items feature is disabled")


# Attach the dependency to all routes in this router. If the feature is disabled,
# every request will immediately raise the above error.
router = APIRouter(dependencies=[Depends(_require_workitems_enabled)])
logger = get_logger(__name__)


async def _validate_callbacks(callbacks: list[WorkItemCallback] | None) -> list[WorkItemCallback]:
    """Validate the callbacks match the supported implementation for workitem callbacks."""
    if not callbacks:
        return []

    seen_callback_states = set()

    for callback in callbacks:
        if not callback.url:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST.value,
                detail="Callback URL is required",
            )

        if callback.on_status in seen_callback_states:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST.value,
                detail=f"Multiple callbacks for a status ({callback.on_status}) are not allowed",
            )

        seen_callback_states.add(callback.on_status)

    return callbacks


@router.post("/", response_model=WorkItem)
async def create_work_item(
    payload: CreateWorkItemPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> WorkItem:
    agent = await storage.get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Agent not found")
    if payload.work_item_id is not None:
        logger.info(f"Work item ID provided: {payload.work_item_id}")
        work_item = await storage.get_work_item(payload.work_item_id)
        if not work_item:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND.value, detail="Work item not found"
            )
        if work_item.status != WorkItemStatus.PRECREATED:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST.value,
                detail="Work item is not in initializing state",
            )

        # Ensure the requested callbacks are supported by the WorkItems service
        payload.callbacks = await _validate_callbacks(payload.callbacks)
        work_item.callbacks = payload.callbacks

        # set agent ID as it wouldn't have been set before.
        work_item.agent_id = payload.agent_id
        work_item.messages = [
            ThreadMessage.model_validate(msg.model_dump()) for msg in payload.messages
        ]
        await storage.update_work_item(work_item)
        # set work item status to pending
        await storage.update_work_item_status(
            user.user_id, work_item.work_item_id, WorkItemStatus.PENDING
        )
        # Update the work_item object to reflect the new status
        work_item.status = WorkItemStatus.PENDING
    else:
        logger.info("No work item ID provided")

        # Ensure the requested callbacks are supported by the WorkItems service
        payload.callbacks = await _validate_callbacks(payload.callbacks)

        work_item = CreateWorkItemPayload.to_work_item(payload=payload, user_id=user.user_id)
        await storage.create_work_item(work_item)

    return work_item


@router.get("/{work_item_id}", response_model=WorkItem)
async def get_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    include_results: bool = Query(
        False,
        alias="results",
        description="Whether to include the results of the work item",
    ),
) -> WorkItem:
    work_item = await storage.get_work_item(work_item_id)
    if not include_results:
        work_item.messages = []
    return work_item


@router.post("/upload-file")
async def upload_work_item_file(
    file: UploadFile,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    work_item_id: str | None = None,
) -> dict[str, str]:
    """Upload a file to a work item. If a work_item_id is not provided, a new one is created."""
    logger.info(f"Uploading file {file.filename} to work item {work_item_id}")
    if work_item_id:
        logger.info(f"Work item ID provided: {work_item_id}")
        if (work_item := await storage.get_work_item(work_item_id)) is None:
            raise HTTPException(status_code=404, detail="Work item not found")
        if work_item.status != WorkItemStatus.PRECREATED:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST.value,
                detail="Work item is not in precreated state",
            )
        logger.info(f"Work item ID from work item: {work_item.work_item_id}")
    else:
        logger.info("No work item ID provided")
        # Stub creation
        work_item = WorkItem(
            user_id=user.user_id,
            messages=[],
            payload={},
            work_item_id=str(uuid4()),
            status=WorkItemStatus.PRECREATED,
        )
        await storage.create_work_item(work_item)

    # A real user uploads the file, but we store it in the file_owners table as the system_user.
    system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)
    logger.info(
        f"Uploading files to work item {work_item.work_item_id} on behalf of user {user.user_id}"
    )
    existing_files = await storage.get_workitem_files(work_item.work_item_id, system_user.user_id)
    for f in existing_files:
        if f.file_ref == file.filename:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST.value,
                detail=f"File {f.file_ref} already exists in work item {work_item.work_item_id}",
            )
    upload_request = [UploadFilePayload(file=file)]
    await file_manager.upload(upload_request, work_item, system_user.user_id)

    return {
        "work_item_id": work_item.work_item_id,
    }


@router.get("/", response_model=list[WorkItem])
async def list_work_items(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = Query(
        None,
        description="The ID of the agent to filter by",
    ),
    limit: int = Query(100, description="The maximum number of work items to return"),
) -> list[WorkItem]:
    return await storage.list_work_items(user.user_id, agent_id=agent_id, limit=limit)


@router.post("/{work_item_id}/continue", response_model=WorkItem)
async def continue_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    item = await storage.update_work_item_status(user.user_id, work_item_id, WorkItemStatus.PENDING)
    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Not found")
    return item


@router.post("/{work_item_id}/restart", response_model=WorkItem)
async def restart_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    item = await storage.update_work_item_status(user.user_id, work_item_id, WorkItemStatus.PENDING)
    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Not found")
    return item


@router.post("/{work_item_id}/cancel")
async def cancel_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    await storage.update_work_item_status(user.user_id, work_item_id, WorkItemStatus.CANCELLED)
    return {"status": "ok"}
