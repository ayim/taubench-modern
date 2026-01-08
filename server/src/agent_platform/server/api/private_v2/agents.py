import asyncio
import typing
import uuid
from collections import defaultdict
from http import HTTPStatus
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException, Request
from structlog import get_logger

from agent_platform.core.actions.action_package import ActionDetail, ActionPackage, ActionPackageDetail, AgentDetails
from agent_platform.core.agent import AgentUserInterface
from agent_platform.core.agent.agent import Agent
from agent_platform.core.data_connections.data_connections import DataConnection
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.files import UploadedFile
from agent_platform.core.mcp.mcp_types import MCPServerDetail, MCPToolDetail
from agent_platform.core.payloads import (
    ActionServerConfigPayload,
    AgentPackagePayload,
    PatchAgentPayload,
    SetAgentDataConnectionsPayload,
    SetAgentSemanticDataModelsPayload,
    UpsertAgentPayload,
)
from agent_platform.core.utils import SecretString
from agent_platform.core.utils.url import safe_urljoin
from agent_platform.server.api.agent_filters import filter_hidden_agents
from agent_platform.server.api.dependencies import AgentQuotaCheck, PlatformParamsValidationCheck, StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache

if typing.TYPE_CHECKING:
    from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

router = APIRouter()
logger = get_logger(__name__)


class ActionPackageData(TypedDict):
    """Structure for action package data returned by fetch functions."""

    actions: list[str]
    version: str


def _to_human_friendly_name(name: str) -> str:
    """Convert action package/action name to human-friendly versions."""
    # Step 1: Replace hyphens and underscores with spaces
    formatted = name.replace("-", " ").replace("_", " ")

    # Step 2: Split camelCase words by inserting spaces before uppercase letters
    import re

    formatted = re.sub(r"([a-z])([A-Z])", r"\1 \2", formatted)

    # Step 3: Title case each word (capitalize first letter, lowercase the rest)
    return " ".join(word.title() for word in formatted.split())


def _metadata_contains(candidate_metadata: object, required_metadata: dict[str, Any]) -> bool:
    """Return True if candidate metadata contains all required key/value pairs."""
    if not isinstance(candidate_metadata, dict):
        return False

    return all(candidate_metadata.get(key) == value for key, value in required_metadata.items())


async def _fetch_action_packages_data(url: str, api_key: str) -> dict[str, ActionPackageData]:
    """Fetch action packages data directly from /api/actionPackages endpoint."""
    from aiohttp import ClientSession

    http_url = "http://" + url if not url.startswith("http") else url
    action_packages_url = safe_urljoin(http_url, "api/actionPackages")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with ClientSession() as session:
        async with session.get(action_packages_url, headers=headers) as response:
            if response.status == HTTPStatus.OK:
                action_packages_data = await response.json()
                logger.info(f"Successfully fetched action packages from {action_packages_url}")

                # Convert list format to dict format with human-friendly names
                packages_dict = {}
                for package in action_packages_data:
                    package_name = package.get("name", "")
                    package_version = package.get("version", "1.0.0")
                    package_actions = package.get("actions", [])

                    if not package_name:
                        continue

                    # Convert to human-friendly name
                    friendly_package_name = _to_human_friendly_name(package_name)

                    # Extract action names (handle both string and dict formats)
                    action_names = []
                    for action in package_actions:
                        if isinstance(action, str):
                            action_names.append(_to_human_friendly_name(action))
                        elif isinstance(action, dict) and "name" in action:
                            action_names.append(_to_human_friendly_name(action["name"]))

                    packages_dict[friendly_package_name] = {
                        "version": package_version,
                        "actions": action_names,
                    }

                return packages_dict
            else:
                logger.error(f"ActionPackages endpoint returned {response.status}")
                raise Exception(f"HTTP {response.status}: Failed to fetch action packages")


async def _process_single_action_package_url(url: str, packages: list[ActionPackage]) -> list[ActionPackageDetail]:
    """Process action packages from a single URL and return their details."""
    action_details = []
    try:
        # Get the first package to extract api_key (they should all be the same for same URL)
        api_key = packages[0].api_key.get_secret_value() if packages[0].api_key else ""

        # Fetch action packages data from /api/actionPackages
        action_packages_data = await _fetch_action_packages_data(url, api_key)

        # Create package details directly from server response
        for pkg_name, package_info in action_packages_data.items():
            actions = package_info.get("actions", [])
            version = package_info.get("version", "1.0.0")
            package_actions = [ActionDetail(name=action) for action in actions]

            # Only create package if it has actions
            if package_actions:
                action_package_details = ActionPackageDetail(
                    name=pkg_name,
                    actions=package_actions,
                    version=version,
                    status="online",
                )
                action_details.append(action_package_details)

    except Exception as e:
        logger.error(f"Error processing action packages from {url}: {e}")
        for package in packages:
            action_package_details = ActionPackageDetail(
                name=package.name,
                actions=[],
                version=package.version,
                status="offline",
                status_details=str(e),
            )
            action_details.append(action_package_details)

    return action_details


async def _process_action_packages(agent) -> list[ActionPackageDetail]:
    """Process action packages and return their details."""
    all_action_details = []

    # Group action packages by URL to avoid duplicate calls
    url_to_packages = defaultdict(list)
    for action_package in agent.action_packages:
        if action_package.url:
            url_to_packages[action_package.url].append(action_package)

    # Fetch action packages data concurrently for all unique URLs
    if url_to_packages:
        for result in await asyncio.gather(
            *[_process_single_action_package_url(url, packages) for url, packages in url_to_packages.items()],
        ):
            all_action_details.extend(result)

    return all_action_details


async def _process_single_mcp_server(
    user: AuthedUser,
    storage: StorageDependency,
    mcp_server_with_oauth_config: "MCPServerWithOAuthConfig",
    selected_tool_names: list[str],
    has_selected_tools: bool,
) -> MCPServerDetail:
    """Process a single MCP server and return its details."""
    from agent_platform.core.tools.tool_definition import ToolCallContext

    try:
        tool_defs = await mcp_server_with_oauth_config.to_tool_definitions(
            storage=storage,
            tool_call_context=ToolCallContext(
                user_id=user.user_id,
                agent_id=None,
                tenant_id=None,
                thread_id=None,
            ),
        )

        allowed_actions = [
            # Only filter out MCP tools based on SelectedTools if there are any SelectedTools present.
            MCPToolDetail(name=tool_def.name)
            for tool_def in tool_defs
            if (not has_selected_tools or tool_def.name in selected_tool_names)
        ]

        return MCPServerDetail(
            name=mcp_server_with_oauth_config.name,
            actions=allowed_actions,
            status="online",
        )
    except Exception as e:
        logger.error(f"Error getting tool definitions for MCP server {mcp_server_with_oauth_config.name}: {e}")
        return MCPServerDetail(
            name=mcp_server_with_oauth_config.name,
            actions=[],
            status="offline",
            status_details=str(e),
        )


async def _process_mcp_servers(agent: Agent, storage: StorageDependency, user: AuthedUser) -> list[MCPServerDetail]:
    """Process MCP servers and return their details."""
    from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

    mcp_servers_dict: dict[str, MCPServerWithOAuthConfig] = await storage.get_mcp_servers_and_oauth_info_by_ids(
        agent.mcp_server_ids
    )
    all_mcp_servers: list[MCPServerWithOAuthConfig] = list(mcp_servers_dict.values())

    if agent.mcp_servers:
        logger.warning("Agent.mcp_servers is deprecated. Use mcp_server_ids instead.")

        for mcp_server in agent.mcp_servers:
            # Old-deprecated MCP servers don't have OAuth configuration
            all_mcp_servers.append(
                MCPServerWithOAuthConfig.model_validate(
                    mcp_server.model_dump(),
                )
            )

    # Collect tool definitions concurrently
    selected_tools = agent.selected_tools.tools if agent.selected_tools else []
    selected_tool_names = [tool.name for tool in selected_tools]
    has_selected_tools = len(selected_tool_names) > 0

    # Execute all tool definition collection concurrently
    all_mcp_server_details: list[MCPServerDetail] = list(
        await asyncio.gather(
            *[
                _process_single_mcp_server(user, storage, mcp_server, selected_tool_names, has_selected_tools)
                for mcp_server in all_mcp_servers
            ],
        )
    )

    return all_mcp_server_details


@router.post("/", response_model=AgentCompat)
async def create_agent(
    payload: UpsertAgentPayload,
    user: AuthedUser,
    storage: StorageDependency,
    _quota: AgentQuotaCheck,
    _validation: PlatformParamsValidationCheck,
) -> AgentCompat:
    from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator

    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id)
    await storage.upsert_agent(user.user_id, agent)

    # Reload orchestrator to include new agent in routing map
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info(f"Reloaded orchestrator after creating agent {agent.agent_id}")

    return AgentCompat.from_agent(agent)


@router.get("/", response_model=list[AgentCompat])
async def list_agents(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentCompat]:
    agents = filter_hidden_agents(await storage.list_agents(user.user_id))
    return [AgentCompat.from_agent(a) for a in agents]


@router.get(
    "/search/by-metadata",
    response_model=list[AgentCompat],
    summary="Find agents by metadata",
    description=("Provide metadata key/value pairs as query parameters (e.g., ?project=xyz&visibility=hidden)."),
)
async def search_agents_by_metadata(
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
) -> list[AgentCompat]:
    required_metadata = dict(request.query_params)
    if not required_metadata:
        raise HTTPException(
            status_code=400,
            detail="At least one metadata query parameter is required.",
        )

    agents = await storage.list_agents(user.user_id)
    return [
        AgentCompat.from_agent(agent)
        for agent in agents
        if _metadata_contains((agent.extra or {}).get("metadata"), required_metadata)
    ]


# Backwards compatibility
@router.get("/raw", response_model=list[AgentCompat])
async def list_agents_raw(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentCompat]:
    agents = filter_hidden_agents(await storage.list_agents(user.user_id))
    return [AgentCompat.from_agent(a, reveal_sensitive=True) for a in agents]


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
    ToolDefinitionCache().clear_for_agent(agent)


@router.put("/{aid}", response_model=AgentCompat)
async def update_agent(
    user: AuthedUser,
    aid: str,
    payload: UpsertAgentPayload,
    storage: StorageDependency,
    _validation: PlatformParamsValidationCheck,
) -> AgentCompat:
    existing_agent = await storage.get_agent(user.user_id, aid)
    agent = UpsertAgentPayload.to_agent(
        payload,
        user_id=user.user_id,
        agent_id=aid,
        existing_agent=existing_agent,
    )
    await storage.upsert_agent(user.user_id, agent)

    ToolDefinitionCache().clear_for_agent(agent)
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
    _validation: PlatformParamsValidationCheck,
) -> AgentCompat:
    existing_agent = await storage.get_agent(user.user_id, aid)
    agent = UpsertAgentPayload.to_agent(
        payload,
        user_id=user.user_id,
        agent_id=aid,
        existing_agent=existing_agent,
    )
    await storage.upsert_agent(user.user_id, agent)

    ToolDefinitionCache().clear_for_agent(agent)
    return AgentCompat.from_agent(agent, reveal_sensitive=True)


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
                api_key=(SecretString(payload.api_key) if isinstance(payload.api_key, str) else payload.api_key),
                allowed_actions=action_package.allowed_actions,
            )
            for action_package in agent.action_packages
        ],
    )

    await storage.upsert_agent(user.user_id, new_agent)
    ToolDefinitionCache().clear_for_agent(new_agent)
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
    return AgentCompat.from_agent(
        await storage.get_agent(user.user_id, aid),
        reveal_sensitive=True,
    )


@router.delete("/{aid}", status_code=204)
async def delete_agent(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> None:
    from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator

    await storage.delete_agent(user.user_id, aid)

    # Reload orchestrator to remove deleted agent from routing map
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info(f"Reloaded orchestrator after deleting agent {aid}")


@router.post("/package", response_model=AgentCompat)
async def create_agent_from_package(
    user: AuthedUser,
    payload: AgentPackagePayload,
    storage: StorageDependency,
    _: AgentQuotaCheck,
) -> AgentCompat:
    aid = str(uuid.uuid4())
    from agent_platform.server.api.private_v2.package import upsert_agent_from_package

    return await upsert_agent_from_package(
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
    from agent_platform.server.api.private_v2.package import upsert_agent_from_package

    return await upsert_agent_from_package(
        user=user,
        aid=aid,
        payload=payload,
        storage=storage,
    )


@router.get("/{aid}/agent-details", response_model=AgentDetails)
async def get_agent_details(
    user: AuthedUser,
    aid: str,
    storage: StorageDependency,
) -> AgentDetails:
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message="Agent not found")

    action_packages, mcp_servers = await asyncio.gather(
        _process_action_packages(agent),
        _process_mcp_servers(agent, storage, user),
    )

    return AgentDetails(
        runbook=agent.runbook_structured.raw_text,
        action_packages=action_packages,
        mcp_servers=mcp_servers,
    )


# Agent Data Connections endpoints
@router.put("/{aid}/data-connections", response_model=list[DataConnection])
async def set_agent_data_connections(
    aid: str,
    payload: SetAgentDataConnectionsPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[DataConnection]:
    """Set data connections for an agent (replace all existing associations)."""
    # Verify agent exists and belongs to user
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Set the data connections
    await storage.set_agent_data_connections(aid, payload.data_connection_ids)

    # Return the updated data connections
    return await storage.get_agent_data_connections(aid)


@router.get("/{aid}/data-connections", response_model=list[DataConnection])
async def get_agent_data_connections(
    aid: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[DataConnection]:
    """Get data connections associated with an agent."""
    # Verify agent exists and belongs to user
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Return the data connections
    return await storage.get_agent_data_connections(aid)


# Agent Semantic Data Models endpoints
@router.put("/{aid}/semantic-data-models", response_model=list[dict])
async def set_agent_semantic_data_models(
    aid: str,
    payload: SetAgentSemanticDataModelsPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[dict]:
    """Set semantic data models for an agent (replace all existing associations)."""
    # Verify agent exists and belongs to user
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Set the semantic data models
    await storage.set_agent_semantic_data_models(aid, payload.semantic_data_model_ids)

    # Return the updated semantic data models
    return await storage.get_agent_semantic_data_models(aid)


@router.get("/{aid}/semantic-data-models", response_model=list[dict])
async def get_agent_semantic_data_models(
    aid: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[dict]:
    """Get semantic data models associated with an agent."""
    # Verify agent exists and belongs to user
    agent = await storage.get_agent(user.user_id, aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Return the semantic data models
    return await storage.get_agent_semantic_data_models(aid)


@router.get("/{agent_id}/user-interfaces", response_model=list[AgentUserInterface])
async def get_agent_user_interfaces(
    agent_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentUserInterface]:
    """Get user interfaces associated with an agent."""
    # Verify agent exists and belongs to user
    agent = await storage.get_agent(user.user_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent.get_user_interfaces()
