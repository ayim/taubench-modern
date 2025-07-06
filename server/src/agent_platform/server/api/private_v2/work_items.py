from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query
from structlog import get_logger

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.payloads.create_work_item import CreateWorkItemPayload
from agent_platform.core.work_items.work_item import WorkItem, WorkItemStatus
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser
from agent_platform.server.constants import SystemConfig


def _require_workitems_enabled():
    """Raise an error if work items are disabled in configuration."""
    if not SystemConfig.enable_workitems:
        raise PlatformHTTPError(ErrorCode.FORBIDDEN, "Work items feature is disabled")


# Attach the dependency to all routes in this router. If the feature is disabled,
# every request will immediately raise the above error.
router = APIRouter(dependencies=[Depends(_require_workitems_enabled)])
logger = get_logger(__name__)


@router.post("/", response_model=WorkItem)
async def create_work_item(
    payload: CreateWorkItemPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> WorkItem:
    work_item = CreateWorkItemPayload.to_work_item(payload, user_id=user.user_id)
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
