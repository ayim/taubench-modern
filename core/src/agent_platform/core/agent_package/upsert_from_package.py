import json

from fastapi import HTTPException
from starlette import status

from agent_platform.core import MCPServer
from agent_platform.core.actions import ActionPackage
from agent_platform.core.agent import AgentArchitecture
from agent_platform.core.agent_package.read import read_and_validate_agent_package
from agent_platform.core.agent_package.semantic_data_models.upsert_from_package import (
    upsert_semantic_data_models,
)
from agent_platform.core.payloads import AgentPackagePayload, UpsertAgentPayload
from agent_platform.core.payloads.agent_package import (
    AgentPackagePayloadActionServer,
    AgentPackagePayloadLangsmith,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.api import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache
from agent_platform.server.storage import AgentNotFoundError


async def upsert_agent_from_package(  # noqa: C901, PLR0912, PLR0915
    user: AuthedUser,
    aid: str,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    # Validate that exactly one of URL or base64 is provided
    sources = [payload.agent_package_url, payload.agent_package_base64]
    non_none_sources = [s for s in sources if s is not None]

    if len(non_none_sources) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specify exactly one of 'agent_package_url' or 'agent_package_base64'",
        )

    # We do a 3 step dance here: wetake the payload, and extract the agent
    # spec and runbook from it (and knowledge files... but ignore those for now)
    agent_package = await read_and_validate_agent_package(
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

    # TODO (agent-cli sunset):
    # Langsmith support for Package import should most likely be dropped.
    #
    # Normalize and bring over langsmith config from payload (accept dict or typed)
    advanced_config = {}
    ls_obj = payload.langsmith
    # If sent via multipart as a JSON string, coerce to dict first
    if isinstance(ls_obj, str):
        try:
            parsed = json.loads(ls_obj)
            ls_obj = parsed if isinstance(parsed, dict) else None
        except Exception:
            ls_obj = None
    if isinstance(ls_obj, dict):  # type: ignore[truthy-bool]
        try:
            ls_obj = AgentPackagePayloadLangsmith(**ls_obj)
        except Exception:
            ls_obj = None
    if ls_obj is not None:
        advanced_config["langsmith"] = ls_obj.model_dump()

    # Bring over action server config from payload (if it's there)
    # NOTE: just as in v1 code, we only can take the first action server
    # here (seems the idea of having multiple was never used...)
    action_server_url = None
    action_server_api_key = None
    normalized_action_servers: list[AgentPackagePayloadActionServer] = []
    # If action_servers came as JSON string via multipart, parse it first
    action_servers_input = payload.action_servers
    if isinstance(action_servers_input, str):
        try:
            parsed = json.loads(action_servers_input)
            if isinstance(parsed, dict):
                action_servers_input = [parsed]
            elif isinstance(parsed, list):
                action_servers_input = parsed
            else:
                action_servers_input = []
        except Exception:
            action_servers_input = []

    if action_servers_input:
        for item in action_servers_input:
            if isinstance(item, AgentPackagePayloadActionServer):
                normalized_action_servers.append(item)
            elif isinstance(item, dict):  # type: ignore[unreachable]
                try:
                    normalized_action_servers.append(AgentPackagePayloadActionServer(**item))
                except Exception:
                    continue
        if normalized_action_servers:
            action_server_url = normalized_action_servers[0].url
            action_server_api_key = normalized_action_servers[0].api_key
    if isinstance(action_server_api_key, str):
        action_server_api_key = SecretString(action_server_api_key)

    # Normalize fields that may arrive as JSON strings from multipart forms
    # mcp_servers: expecting a list of dicts or MCPServer objects
    mcp_input = payload.mcp_servers
    if isinstance(mcp_input, str):
        try:
            parsed = json.loads(mcp_input)
            if isinstance(parsed, dict):
                mcp_input = [parsed]
            elif isinstance(parsed, list):
                mcp_input = parsed
        except Exception:
            mcp_input = []

    normalized_mcp_servers = []
    for server in mcp_input:
        if isinstance(server, dict):  # type: ignore[unreachable]
            normalized_mcp_servers.append(MCPServer.model_validate(server))
        else:
            normalized_mcp_servers.append(server)

    # Normalize mcp_server_ids in case multipart left it as a JSON string
    mcp_server_ids: list[str] = []
    mcp_ids_input = payload.mcp_server_ids
    if isinstance(mcp_ids_input, str):
        try:
            parsed = json.loads(mcp_ids_input)
            if isinstance(parsed, list):
                mcp_server_ids = [x for x in parsed if isinstance(x, str)]
        except Exception:
            mcp_server_ids = []
    elif isinstance(mcp_ids_input, list):
        mcp_server_ids = [x for x in mcp_ids_input if isinstance(x, str)]

    # Normalize platform_params_ids in case multipart left it as a JSON string
    platform_params_ids: list[str] = []
    platform_params_ids_input = payload.platform_params_ids
    if isinstance(platform_params_ids_input, str):
        try:
            parsed = json.loads(platform_params_ids_input)
            if isinstance(parsed, list):
                platform_params_ids = [x for x in parsed if isinstance(x, str)]
        except Exception:
            platform_params_ids = []
    elif isinstance(platform_params_ids_input, list):
        platform_params_ids = [x for x in platform_params_ids_input if isinstance(x, str)]

    # Normalize model in case multipart parsing left it as a JSON string
    normalized_model = payload.model
    if isinstance(normalized_model, str):
        try:
            normalized_model = json.loads(normalized_model)
        except Exception:
            normalized_model = None

    # Original architecture name (if not present, use default)
    mapped_architecture_name = agent0.get("architecture", "agent_platform.architectures.default")
    if not mapped_architecture_name.startswith("agent_platform.architectures."):
        # If we have any legacy value, use default
        mapped_architecture_name = "agent_platform.architectures.default"

    as_upsert_payload = UpsertAgentPayload(
        name=payload.name,  # Want name from payload, not agent project
        description=payload.description
        if payload.description is not None
        else agent0.get("description", ""),
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
        mcp_servers=normalized_mcp_servers,
        mcp_server_ids=mcp_server_ids,
        selected_tools=payload.selected_tools,
        platform_params_ids=platform_params_ids,
        runbook=agent_package.runbook_text,
        advanced_config=advanced_config,
        question_groups=agent_package.question_groups,
        agent_settings=agent_package.agent_settings or {},
        extra={
            "conversation_starter": agent_package.conversation_starter,
            "welcome_message": agent_package.welcome_message,
            "agent_settings": agent_package.agent_settings,
        },
        model=normalized_model,
        agent_architecture=AgentArchitecture(
            # Take architecture name from package, force
            # version to 1.0.0 (we don't support arch versioning yet
            # across the stack)
            name=mapped_architecture_name,
            version="1.0.0",
        ),
        metadata={
            **agent0.get("metadata", {}),
        },
        document_intelligence=agent0.get("document-intelligence", None),
    )

    # Now, for the third and final step, we have essentially a normal
    # agent create (just as the upsert_agent endpoint does)
    try:
        existing_agent = await storage.get_agent(user.user_id, aid)
    except AgentNotFoundError:
        existing_agent = None

    as_agent = UpsertAgentPayload.to_agent(
        payload=as_upsert_payload,
        agent_id=aid,
        user_id=user.user_id,
        existing_agent=existing_agent,
    )
    await storage.upsert_agent(user.user_id, as_agent)

    # Import semantic data models if present in the package
    await upsert_semantic_data_models(
        agent_id=aid,
        sdms=agent_package.semantic_data_models,
        storage=storage,
    )

    # We might technically clear on a create here, which shouldn't be
    # problem (even if it's not strictly necessary)
    ToolDefinitionCache().clear_for_agent(as_agent)
    return AgentCompat.from_agent(as_agent)
