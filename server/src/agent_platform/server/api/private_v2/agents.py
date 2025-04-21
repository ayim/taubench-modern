from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.payloads import UpsertAgentPayload
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=Agent)
async def create_agent(
    payload: UpsertAgentPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> Agent:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id)
    await storage.upsert_agent(user.user_id, agent)
    return agent


# TODO: raw ("show secrets") vs masked ("no secrets")?
@router.get("/", response_model=list[Agent])
async def list_agents(user: AuthedUser, storage: StorageDependency) -> list[Agent]:
    return await storage.list_agents(user.user_id)


@router.get("/by-name", response_model=Agent)
async def get_agent_by_name(
    user: AuthedUser,
    name: str,
    storage: StorageDependency,
) -> Agent:
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    return await storage.get_agent_by_name(user.user_id, name)


@router.get("/{aid}", response_model=Agent)
async def get_agent(user: AuthedUser, aid: str, storage: StorageDependency) -> Agent:
    return await storage.get_agent(user.user_id, aid)


@router.delete("/{aid}", status_code=204)
async def delete_agent(user: AuthedUser, aid: str, storage: StorageDependency) -> None:
    await storage.delete_agent(user.user_id, aid)
