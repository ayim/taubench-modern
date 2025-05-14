import uuid

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import AgentArchitecture
from agent_platform.core.agent_spec.extract_spec import (
    extract_and_validate_agent_package,
)
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import (
    ActionServerConfigPayload,
    AgentPackagePayload,
    PatchAgentPayload,
    UpsertAgentPayload,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools import AgentServerToolsInterface

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


@router.post("/{aid}/refresh-tools", status_code=204)
async def refresh_tools(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> None:
    agent = await storage.get_agent(user.user_id, aid)
    AgentServerToolsInterface.clear_tools_for_agent(agent)


@router.put("/{aid}", response_model=AgentCompat)
async def update_agent(
    user: AuthedUser,
    aid: str,
    payload: UpsertAgentPayload,
    storage: StorageDependency,
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id, agent_id=aid)
    await storage.upsert_agent(user.user_id, agent)
    AgentServerToolsInterface.clear_tools_for_agent(agent)
    return AgentCompat.from_agent(agent)


@router.patch("/{aid}", response_model=AgentCompat)
async def patch_agent(
    user: AuthedUser,
    aid: str,
    payload: PatchAgentPayload,
    storage: StorageDependency,
) -> AgentCompat:
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await storage.patch_agent(user.user_id, aid, payload.name, payload.description)
    # Just updates name/description, so no need to clear tools
    return AgentCompat.from_agent(await storage.get_agent(user.user_id, aid))


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
    AgentServerToolsInterface.clear_tools_for_agent(agent)
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
    AgentServerToolsInterface.clear_tools_for_agent(new_agent)
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


async def _create_or_update_agent_from_package(
    user: AuthedUser,
    aid: str,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    # We do a 3 step dance here: wetake the payload, and extract the agent
    # spec and runbook from it (and knowledge files... but ignore those for now)
    agent_package = await extract_and_validate_agent_package(
        path=None,  # No local path option here: either URL or base64
        url=payload.agent_package_url,
        package_base64=payload.agent_package_base64,
        include_knowledge=False,
        knowledge_return="stream",
    )

    # The spec _must_ be the v2 agent spec; which represents "v1 agents"
    # from our perspective. So we use UpsertAgentPayload to re-use our
    # legacy conversion logic and get a "v2 agent" out of it.
    agent0 = agent_package.spec["agent-package"]["agents"][0]

    # Bring over langsmith config from payload
    advanced_config = {}
    if payload.langsmith:
        advanced_config["langsmith"] = payload.langsmith

    # Bring over action server config from payload (if it's there)
    # NOTE: just as in v1 code, we only can take the first action server
    # here (seems the idea of having multiple was never used...)
    action_server_url = None
    action_server_api_key = None
    if len(payload.action_servers) > 0:
        action_server_url = payload.action_servers[0].url
        action_server_api_key = payload.action_servers[0].api_key
    if isinstance(action_server_api_key, str):
        action_server_api_key = SecretString(action_server_api_key)

    as_upsert_payload = UpsertAgentPayload(
        name=payload.name,  # Want name from payload, not agent project
        description=agent0.get("description", ""),
        version=agent0.get("version", "1.0.0"),
        action_packages=[
            ActionPackage(
                name=action_package["name"],
                organization=action_package["organization"],
                version=action_package["version"],
                url=action_server_url,
                api_key=action_server_api_key,
            )
            for action_package in agent0.get("action-packages", [])
        ],
        runbook=agent_package.runbook_text,
        advanced_config=advanced_config,
        model=payload.model,
        agent_architecture=AgentArchitecture(
            # Doesn't matter what we were given, all legacy architectures
            # get mapped to default for v2
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
    )

    # Now, for the third and final step, we have essentially a normal
    # agent create (just as the upsert_agent endpoint does)
    as_agent = UpsertAgentPayload.to_agent(
        payload=as_upsert_payload,
        agent_id=aid,
        user_id=user.user_id,
    )
    await storage.upsert_agent(user.user_id, as_agent)
    # We might technically clear on a create here, which shouldn't be
    # problem (even if it's not strictly necessary)
    AgentServerToolsInterface.clear_tools_for_agent(as_agent)
    return AgentCompat.from_agent(as_agent)


@router.post("/package", response_model=AgentCompat)
async def create_agent_from_package(
    user: AuthedUser,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    aid = str(uuid.uuid4())
    return await _create_or_update_agent_from_package(
        user=user,
        aid=aid,
        payload=payload,
        storage=storage,
    )


@router.put("/package/{aid}", response_model=AgentCompat)
async def update_agent_from_package(
    user: AuthedUser,
    aid: str,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    return await _create_or_update_agent_from_package(
        user=user,
        aid=aid,
        payload=payload,
        storage=storage,
    )
