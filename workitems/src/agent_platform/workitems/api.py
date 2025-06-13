from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .crud import (
    cancel_work_item,
    create_work_item,
    get_work_item,
    list_work_items,
    update_status,
)
from .db import instance
from .models import CreateWorkItemPayload, WorkItem, WorkItemStatus

router = APIRouter(
    prefix="/v1/work-items",
    tags=["work-items"],
)


def get_db_session(request: Request):
    with instance.session() as session:
        yield session


# Create module-level dependency
_db_session = Depends(get_db_session)


@router.post("/", response_model=WorkItem)
async def create_item(
    item: CreateWorkItemPayload,
    session=_db_session,
):
    work_item = await create_work_item(session, item)
    return work_item


@router.get("/{work_item_id}", response_model=WorkItem)
async def describe_work_item(
    work_item_id: str,
    include_results: bool = Query(False, alias="results"),
    session=_db_session,
):
    work_item = await get_work_item(session, work_item_id)
    if not work_item:
        raise HTTPException(status_code=404, detail="Not found")
    if not include_results:
        work_item.messages = []
    return work_item


@router.get("/", response_model=list[WorkItem])
async def list_items(limit: int = 100, session=_db_session):
    items = await list_work_items(session, limit)
    return items


@router.post("/{work_item_id}/continue", response_model=WorkItem)
async def continue_work_item(work_item_id: str, session=_db_session):
    item = await update_status(session, work_item_id, WorkItemStatus.PENDING, "SYSTEM")
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.post("/{work_item_id}/restart", response_model=WorkItem)
async def restart_work_item(work_item_id: str, session=_db_session):
    item = await update_status(session, work_item_id, WorkItemStatus.PENDING, "SYSTEM")
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.post("/{work_item_id}/cancel")
async def cancel_item(work_item_id: str, session=_db_session):
    await cancel_work_item(session, work_item_id)
    return {"status": "ok"}
