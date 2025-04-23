from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import ActionServerConfigPayload, UpsertAgentPayload
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=AgentCompat)
async def create_agent(
    payload: UpsertAgentPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id)
    await storage.upsert_agent(user.user_id, agent)
    return AgentCompat.from_agent(agent)


@router.get("/", response_model=list[AgentCompat])
async def list_agents(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentCompat]:
    return [AgentCompat.from_agent(a) for a in await storage.list_agents(user.user_id)]


# Backwards compatibility
@router.get("/raw", response_model=list[AgentCompat])
async def list_agents_raw(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentCompat]:
    return [AgentCompat.from_agent(a) for a in await storage.list_agents(user.user_id)]


@router.get("/by-name", response_model=AgentCompat)
async def get_agent_by_name(
    user: AuthedUser,
    name: str,
    storage: StorageDependency,
) -> AgentCompat:
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    return AgentCompat.from_agent(await storage.get_agent_by_name(user.user_id, name))


@router.put("/{aid}", response_model=AgentCompat)
async def update_agent(
    user: AuthedUser,
    aid: str,
    payload: UpsertAgentPayload,
    storage: StorageDependency,
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id, agent_id=aid)
    await storage.upsert_agent(user.user_id, agent)
    return AgentCompat.from_agent(agent)


# Backwards compatibility
@router.put("/{aid}/raw", response_model=AgentCompat)
async def update_agent_raw(
    user: AuthedUser,
    aid: str,
    payload: UpsertAgentPayload,
    storage: StorageDependency,
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id, agent_id=aid)
    await storage.upsert_agent(user.user_id, agent)
    return AgentCompat.from_agent(agent)


# Backwards compatibility
@router.get("/{aid}/files", response_model=list[UploadedFile])
async def get_agent_files(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> list[UploadedFile]:
    return []


@router.put("/{aid}/action-server-config", response_model=AgentCompat)
async def update_agent_action_server_config(
    user: AuthedUser,
    aid: str,
    payload: ActionServerConfigPayload,
    storage: StorageDependency,
) -> AgentCompat:
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    new_agent = agent.copy(
        action_packages=[
            ActionPackage(
                name=action_package.name,
                organization=action_package.organization,
                version=action_package.version,
                url=payload.url,
                api_key=(
                    SecretString(payload.api_key)
                    if isinstance(payload.api_key, str)
                    else payload.api_key
                ),
                allowed_actions=action_package.allowed_actions,
            )
            for action_package in agent.action_packages
        ],
    )

    await storage.upsert_agent(user.user_id, new_agent)
    return AgentCompat.from_agent(new_agent)


@router.get("/{aid}", response_model=AgentCompat)
async def get_agent(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> AgentCompat:
    return AgentCompat.from_agent(await storage.get_agent(user.user_id, aid))


# Backwards compatibility
@router.get("/{aid}/raw", response_model=AgentCompat)
async def get_agent_raw(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> AgentCompat:
    return AgentCompat.from_agent(await storage.get_agent(user.user_id, aid))


@router.delete("/{aid}", status_code=204)
async def delete_agent(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> None:
    await storage.delete_agent(user.user_id, aid)
