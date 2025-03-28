from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.payloads import UpsertAgentPayload
from sema4ai_agent_server.auth.handlers_v2 import AuthedUserV2
from sema4ai_agent_server.storage.v2 import get_storage_v2

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Agent)
async def create_agent(
    payload: UpsertAgentPayload,
    user: AuthedUserV2,
) -> Agent:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id)
    await get_storage_v2().upsert_agent_v2(user.user_id, agent)
    return agent


# TODO: raw ("show secrets") vs masked ("no secrets")?
@router.get("/", response_model=list[Agent])
async def list_agents(user: AuthedUserV2) -> list[Agent]:
    return await get_storage_v2().list_agents_v2(user.user_id)


@router.get("/by-name", response_model=Agent)
async def get_agent_by_name(user: AuthedUserV2, name: str) -> Agent:
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    return await get_storage_v2().get_agent_by_name_v2(user.user_id, name)


@router.get("/{aid}", response_model=Agent)
async def get_agent(user: AuthedUserV2, aid: str) -> Agent:
    return await get_storage_v2().get_agent_v2(user.user_id, aid)


@router.delete("/{aid}", status_code=204)
async def delete_agent(user: AuthedUserV2, aid: str) -> None:
    await get_storage_v2().delete_agent_v2(user.user_id, aid)
