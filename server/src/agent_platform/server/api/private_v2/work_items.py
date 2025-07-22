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
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemCallback,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.api.dependencies import FileManagerDependency, StorageDependency
from agent_platform.server.api.private_v2.threads import (
    ConfirmRemoteFileUploadPayload,
)
from agent_platform.server.auth import AuthedUser
from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB, SystemConfig
from agent_platform.server.work_items.callbacks import _build_work_item_url
from agent_platform.server.work_items.rest import WorkItemsListResponse
from agent_platform.server.work_items.state_machine import WorkItemStateMachine


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
        # Set the initial messages and messages to the user-provided list of messages.
        # Messages for work-items files are added after the work-item moves to EXECUTING.
        work_item.initial_messages = [
            ThreadMessage.model_validate(msg.model_dump()) for msg in payload.messages
        ]
        work_item.messages = [
            ThreadMessage.model_validate(msg.model_dump()) for msg in payload.messages
        ]
        await storage.update_work_item(work_item)
        # set work item status to pending
        await storage.update_work_item_status(
            user.user_id,
            work_item.work_item_id,
            WorkItemStatus.PENDING,
            WorkItemStatusUpdatedBy.HUMAN,
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
    work_item.work_item_url = (
        _build_work_item_url(work_item) if work_item.thread_id and work_item.agent_id else None
    )
    return work_item


@router.post("/{work_item_id}/confirm-file")
async def confirm_file(
    work_item_id: str,
    payload: ConfirmRemoteFileUploadPayload,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
) -> dict[str, str]:
    """Confirm a remote file upload to a work item."""
    # 1. Ensure the work_item exists
    work_item = await storage.get_work_item(work_item_id)
    if not work_item:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")

    if work_item.status != WorkItemStatus.PRECREATED:
        raise PlatformHTTPError(
            ErrorCode.BAD_REQUEST,
            f"Files can only be attached to work-items in the PRECREATED state."
            f" Currently in {work_item.status}",
        )

    # Check for duplicate file names
    system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)
    existing_files = await storage.get_workitem_files(work_item.work_item_id, system_user.user_id)
    for f in existing_files:
        if f.file_ref == payload.file_ref:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                f"File {f.file_ref} already exists in work item {work_item.work_item_id}",
            )

    # 2. Call file_manager.confirm_remote_file_upload
    await file_manager.confirm_remote_file_upload(
        owner=work_item, file_ref=payload.file_ref, file_id=payload.file_id
    )

    # 3. Return the work_item_id
    return {"work_item_id": work_item_id}


@router.post("/upload-file")
async def upload_work_item_file(
    file: UploadFile | str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    work_item_id: str | None = None,
) -> dict[str, str | dict]:
    """Upload a file to a work item. If a work_item_id is not provided, a new one is created."""
    # Check if this is a request for remote file upload (no actual file data)
    if isinstance(file, str):
        # This is a request for presigned URL, not direct upload
        if work_item_id is None:
            # Create a new work item in PRECREATED state
            work_item = await _create_stub_work_item(user.user_id, storage)
        else:
            work_item = await storage.get_work_item(work_item_id)
            if not work_item:
                raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")
            if work_item.status != WorkItemStatus.PRECREATED:
                raise PlatformHTTPError(
                    ErrorCode.BAD_REQUEST,
                    f"Files can only be attached to work-items in the PRECREATED state."
                    f" Currently in {work_item.status}",
                )

        # Request remote file upload from file manager
        remote_upload_data = await file_manager.request_remote_file_upload(work_item, file)

        return {
            "work_item_id": work_item.work_item_id,
            "upload_url": remote_upload_data.url,
            "upload_form_data": remote_upload_data.form_data,
            "file_id": remote_upload_data.file_id,
            "file_ref": remote_upload_data.file_ref,
        }

    # We have a file directly included in the POST. Upload it and add it to the work_item.
    logger.info(f"Uploading file {file.filename} to work item {work_item_id}")
    if work_item_id:
        logger.info(f"Work item ID provided: {work_item_id}")
        if (work_item := await storage.get_work_item(work_item_id)) is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")
        if work_item.status != WorkItemStatus.PRECREATED:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                f"Files can only be attached to work-items in the PRECREATED state."
                f" Currently in {work_item.status}",
            )
        logger.info(f"Work item ID from work item: {work_item.work_item_id}")
    else:
        logger.info("No work item ID provided")
        # Stub creation
        work_item = await _create_stub_work_item(user.user_id, storage)

    # A real user uploads the file, but we store it in the file_owners table as the system_user.
    system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)
    logger.info(
        f"Uploading files to work item {work_item.work_item_id} on behalf of user {user.user_id}"
    )
    existing_files = await storage.get_workitem_files(work_item.work_item_id, system_user.user_id)
    for f in existing_files:
        if f.file_ref == file.filename:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                f"File {f.file_ref} already exists in work item {work_item.work_item_id}",
            )
    upload_request = [UploadFilePayload(file=file)]
    await file_manager.upload(upload_request, work_item, system_user.user_id)

    return {
        "work_item_id": work_item.work_item_id,
    }


@router.get("/", response_model=WorkItemsListResponse)
async def list_work_items(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = Query(
        None,
        description="The ID of the agent to filter by",
    ),
    limit: int = Query(100, ge=1, description="The maximum number of work items to return"),
    offset: int = Query(0, ge=0, description="The offset to start from"),
) -> WorkItemsListResponse:
    work_items = await storage.list_work_items(
        user.user_id, agent_id=agent_id, limit=limit, offset=offset
    )
    for work_item in work_items:
        work_item.messages = []
        work_item.work_item_url = (
            _build_work_item_url(work_item) if work_item.thread_id and work_item.agent_id else ""
        )

    # if we have fewer than the limit, we have no more work items to fetch
    if len(work_items) < limit:
        next_offset = None
    else:
        next_offset = offset + limit

    return WorkItemsListResponse(records=work_items, next_offset=next_offset)


@router.post("/{work_item_id}/continue", response_model=WorkItem)
async def continue_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    item = await storage.get_work_item(work_item_id)
    if not item:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work-item not found")

    if not WorkItemStateMachine.is_valid_transition(item.status, WorkItemStatus.PENDING):
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            f"Cannot continue work item from status {item.status.value}.",
        )

    await storage.update_work_item_status(
        user.user_id, work_item_id, WorkItemStatus.PENDING, WorkItemStatusUpdatedBy.HUMAN
    )
    return await storage.get_work_item(work_item_id)


@router.post("/{work_item_id}/restart", response_model=WorkItem)
async def restart_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    # Get the current work item to check its status
    work_item = await storage.get_work_item(work_item_id)
    if not work_item:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")

    if not WorkItemStateMachine.is_valid_transition(work_item.status, WorkItemStatus.PENDING):
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            f"Cannot restart work item from status {work_item.status.value}.",
        )

    # Reset the internal state of the work item back to the initial state.
    work_item.restart(user.user_id)
    # Persist the changes to the database.
    await storage.update_work_item(work_item)

    return await storage.get_work_item(work_item_id)


@router.post("/{work_item_id}/cancel")
async def cancel_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    # Get the current work item to check its status
    work_item = await storage.get_work_item(work_item_id)
    if not work_item:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")

    # Check if cancellation is allowed from the current status
    if not WorkItemStateMachine.is_valid_transition(work_item.status, WorkItemStatus.CANCELLED):
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            f"Cannot cancel work item from status {work_item.status.value}.",
        )

    await storage.update_work_item_status(
        user.user_id, work_item_id, WorkItemStatus.CANCELLED, WorkItemStatusUpdatedBy.HUMAN
    )
    return {"status": "ok"}


@router.post("/{work_item_id}/complete")
async def complete_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Administratively mark a work item as completed."""
    work_item = await storage.get_work_item(work_item_id)
    if not work_item:
        raise PlatformHTTPError(ErrorCode.NOT_FOUND, "Work item not found")
    if not WorkItemStateMachine.is_valid_transition(work_item.status, WorkItemStatus.COMPLETED):
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            f"Cannot complete work item from status {work_item.status.value}.",
        )
    await storage.complete_work_item(user.user_id, work_item_id, WorkItemCompletedBy.HUMAN)
    return {"status": "ok"}


async def _create_stub_work_item(user_id: str, storage: StorageDependency) -> WorkItem:
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=user_id,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)
    return work_item
