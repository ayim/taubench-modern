import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .agents.client import AgentClient, FastAPIAgentClient, HttpAgentClient
from .db import instance
from .models import CreateWorkItemPayload, WorkItem, WorkItemStatus
from .services.workitem import AgentValidationError, WorkItemService

router = APIRouter(
    prefix="/v1/work-items",
    tags=["work-items"],
)

logger = logging.getLogger(__name__)


def get_db_session(request: Request):
    with instance.session() as session:
        yield session


def get_agent_client(request: Request) -> AgentClient:
    """
    Get the AgentClient dependency.

    In a real deployment, this might be configured to use different
    implementations or connect to external agent services.
    For now, we'll use a simple mock that always validates.
    """
    agent_app = request.app.state.agent_app
    if agent_app is None:
        url = request.app.state.agent_server_url
        if url is None:
            raise ValueError("agent_app or agent_server_url is required")
        logger.info(f"Using agent server url over HTTP: {url}")
        return HttpAgentClient(url)

    logger.info(f"Using agent app over ASGI: {agent_app}")
    return FastAPIAgentClient(agent_app)


# Create module-level dependencies
_db_session = Depends(get_db_session)
_agent_client = Depends(get_agent_client)


@router.post("/", response_model=WorkItem)
async def create_item(
    item: CreateWorkItemPayload,
    session=_db_session,
    agent_client: AgentClient = _agent_client,
):
    svc = WorkItemService(session, agent_client)
    try:
        work_item = await svc.create(item)
        return work_item
    except AgentValidationError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST.value, detail=str(e)) from e


@router.get("/{work_item_id}", response_model=WorkItem)
async def describe_work_item(
    work_item_id: str,
    include_results: bool = Query(False, alias="results"),
    session=_db_session,
    agent_client: AgentClient = _agent_client,
):
    svc = WorkItemService(session, agent_client)
    work_item = await svc.describe(work_item_id)
    if not work_item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Not found")
    if not include_results:
        work_item.messages = []
    return work_item


@router.get("/", response_model=list[WorkItem])
async def list_items(
    limit: int = 100, session=_db_session, agent_client: AgentClient = _agent_client
):
    svc = WorkItemService(session, agent_client)
    items = await svc.list(limit)
    return items


@router.post("/{work_item_id}/continue", response_model=WorkItem)
async def continue_work_item(
    work_item_id: str, session=_db_session, agent_client: AgentClient = _agent_client
):
    svc = WorkItemService(session, agent_client)
    item = await svc.update_status(work_item_id, WorkItemStatus.PENDING, "SYSTEM")
    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Not found")
    return item


@router.post("/{work_item_id}/restart", response_model=WorkItem)
async def restart_work_item(
    work_item_id: str, session=_db_session, agent_client: AgentClient = _agent_client
):
    svc = WorkItemService(session, agent_client)
    item = await svc.update_status(work_item_id, WorkItemStatus.PENDING, "SYSTEM")
    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND.value, detail="Not found")
    return item


@router.post("/{work_item_id}/cancel")
async def cancel_item(
    work_item_id: str, session=_db_session, agent_client: AgentClient = _agent_client
):
    svc = WorkItemService(session, agent_client)
    await svc.update_status(work_item_id, WorkItemStatus.CANCELLED, "SYSTEM")
    return {"status": "ok"}
