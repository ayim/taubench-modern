from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.payloads import UpsertAgentPayload
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.storage import get_storage

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Agent)
async def create_agent(
    payload: UpsertAgentPayload,
    user: AuthedUser,
) -> Agent:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id)
    await get_storage().upsert_agent(user.user_id, agent)
    return agent


# TODO: raw ("show secrets") vs masked ("no secrets")?
@router.get("/", response_model=list[Agent])
async def list_agents(user: AuthedUser) -> list[Agent]:
    return await get_storage().list_agents(user.user_id)


@router.get("/by-name", response_model=Agent)
async def get_agent_by_name(user: AuthedUser, name: str) -> Agent:
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    return await get_storage().get_agent_by_name(user.user_id, name)


@router.get("/{aid}", response_model=Agent)
async def get_agent(user: AuthedUser, aid: str) -> Agent:
    return await get_storage().get_agent(user.user_id, aid)


@router.delete("/{aid}", status_code=204)
async def delete_agent(user: AuthedUser, aid: str) -> None:
    await get_storage().delete_agent(user.user_id, aid)
