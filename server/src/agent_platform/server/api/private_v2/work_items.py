from fastapi import APIRouter, Query, UploadFile

from agent_platform.core.payloads.create_work_item import CreateWorkItemPayload
from agent_platform.core.payloads.update_work_item import UpdateWorkItemPayload
from agent_platform.core.work_items.work_item import WorkItem, WorkItemStatus
from agent_platform.server.api.dependencies import (
    FileManagerDependency,
    StorageDependency,
    WorkItemFileAttachmentSizeCheck,
    WorkItemPayloadSizeCheck,
)
from agent_platform.server.api.private_v2.threads import ConfirmRemoteFileUploadPayload
from agent_platform.server.auth import AuthedUser
from agent_platform.server.work_items import rest
from agent_platform.server.work_items.rest import (
    AgentWorkItemsSummaryResponse,
    WorkItemsListResponse,
    WorkItemTaskStatusResponse,
)

router = APIRouter()


# Preview work item endpoint (internal use only)
@router.post(
    "/preview",
    include_in_schema=False,  # used only by internal tools (e.g. quality)
)
async def preview_work_item(
    payload: CreateWorkItemPayload,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Preview the status of a work item during a dry run."""
    return await rest.preview_work_item(payload, user, storage)


# Important to register this (top-down) before the GET endpoint (else it will take precedence and
# answer the request).
@router.get("/summary", response_model=list[AgentWorkItemsSummaryResponse])
async def get_work_items_summary(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentWorkItemsSummaryResponse]:
    """Get work items summary grouped by agent and status."""
    # Get summary data from storage (already grouped, counted, and converted to response models)
    return await storage.get_work_items_summary(user.user_id)


##
# Public endpoint
##


# Create work item endpoints
@router.post("/", response_model=WorkItem)
@router.post("", response_model=WorkItem)
async def create_work_item(
    payload: CreateWorkItemPayload,
    user: AuthedUser,
    storage: StorageDependency,
    _: WorkItemPayloadSizeCheck,
) -> WorkItem:
    """Creates a new work item."""
    return await rest.create_work_item(payload, user, storage, _)


# Report work item status endpoint (must be before /{work_item_id} to avoid route collision)
@router.get("/status")
async def report_work_item_status(
    user: AuthedUser,  # for side-effect.
) -> WorkItemTaskStatusResponse:
    """
    Report the status of all work items from the WorkItemsService. If the WorkItemsService
    does not support status, the inner status array will be null.
    """
    return await rest.report_work_item_status()


# Get work item endpoint
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
    """Gets a specific work item by ID."""
    return await rest.get_work_item(work_item_id, user, storage, include_results)


# Confirm file upload endpoint
@router.post("/{work_item_id}/confirm-file")
async def confirm_file(
    work_item_id: str,
    payload: ConfirmRemoteFileUploadPayload,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
) -> dict[str, str]:
    """Confirm a remote file upload to a work item."""
    return await rest.confirm_file(work_item_id, payload, user, storage, file_manager)


# Upload file endpoint
@router.post("/upload-file")
async def upload_work_item_file(
    file: UploadFile | str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    _: WorkItemFileAttachmentSizeCheck,
    work_item_id: str | None = None,
) -> dict[str, str | dict]:
    """Upload a file to a work item. If a work_item_id is not provided, a new one is created."""
    return await rest.upload_work_item_file(file, user, storage, file_manager, _, work_item_id)


# List work items endpoints
@router.get("", response_model=WorkItemsListResponse)
@router.get("/", response_model=WorkItemsListResponse)
async def list_work_items(  # noqa: PLR0913
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = Query(None, description="The ID of the agent to filter by"),
    limit: int = Query(100, ge=1, description="The maximum number of work items to return"),
    offset: int = Query(0, ge=0, description="The offset to start from"),
    created_by: str | None = Query(
        None, description="The ID of the user who created the work items"
    ),
    work_item_status: list[WorkItemStatus] | None = Query(  # noqa: B008
        None, description="Filter by work item status (can specify multiple statuses)"
    ),
    name_search: str | None = Query(None, description="Search in work item name"),
) -> WorkItemsListResponse:
    """Lists all work items."""
    return await rest.list_work_items(
        user, storage, agent_id, limit, offset, created_by, work_item_status, name_search
    )


# Continue work item endpoint
@router.post("/{work_item_id}/continue", response_model=WorkItem)
async def continue_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Continues a specific work item."""
    return await rest.continue_work_item(work_item_id, user, storage)


# Restart work item endpoint
@router.post("/{work_item_id}/restart", response_model=WorkItem)
async def restart_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Restarts a specific work item."""
    return await rest.restart_work_item(work_item_id, user, storage)


# Cancel work item endpoint
@router.post("/{work_item_id}/cancel")
async def cancel_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Cancels a specific work item."""
    return await rest.cancel_item(work_item_id, user, storage)


# Complete work item endpoint
@router.post("/{work_item_id}/complete")
async def complete_work_item(
    work_item_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """Administratively mark a work item as completed."""
    return await rest.complete_work_item(work_item_id, user, storage)


# Update work item endpoint
@router.patch("/{work_item_id}", response_model=WorkItem)
async def update_work_item(
    work_item_id: str,
    payload: UpdateWorkItemPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> WorkItem:
    """Update a work item's properties."""
    return await rest.update_work_item(work_item_id, payload.work_item_name, user, storage)
