import uuid
from collections import defaultdict
from http import HTTPStatus

from aiohttp import ClientSession
from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.actions.action_package import (
    ActionDetail,
    ActionPackage,
    ActionPackageDetail,
    AgentDetails,
)
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.files import UploadedFile
from agent_platform.core.mcp.mcp_types import MCPServerDetail, MCPToolDetail
from agent_platform.core.payloads import (
    ActionServerConfigPayload,
    AgentPackagePayload,
    PatchAgentPayload,
    UpsertAgentPayload,
)
from agent_platform.core.utils import SecretString
from agent_platform.core.utils.url import safe_urljoin
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.api.private_v2.package import create_or_update_agent_from_package
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache

router = APIRouter()
logger = get_logger(__name__)


def _to_human_friendly_name(name: str) -> str:
    """Convert action package/action name to human-friendly versions."""
    # Step 1: Replace hyphens and underscores with spaces
    formatted = name.replace("-", " ").replace("_", " ")

    # Step 2: Split camelCase words by inserting spaces before uppercase letters
    import re

    formatted = re.sub(r"([a-z])([A-Z])", r"\1 \2", formatted)

    # Step 3: Title case each word (capitalize first letter, lowercase the rest)
    return " ".join(word.title() for word in formatted.split())


async def _fetch_action_packages_data(url: str, api_key: str) -> dict[str, list[str]]:
    """Fetch and parse OpenAPI spec to extract action packages from path structure."""

    # Build OpenAPI spec URL
    http_url = "http://" + url if not url.startswith("http") else url
    spec_url = safe_urljoin(http_url, "openapi.json")

    # Fetch OpenAPI spec
    async with ClientSession() as session:
        async with session.get(spec_url) as response:
            if response.status == HTTPStatus.OK:
                spec = await response.json()
            else:
                raise Exception(f"HTTP {response.status}: Failed to fetch OpenAPI spec")

    # Parse paths to extract action packages and actions
    packages_dict = {}

    for path, methods in spec.get("paths", {}).items():
        # Must start with /api/actions
        if not path.startswith("/api/actions"):
            continue

        # Must end with /run
        if not path.endswith("/run"):
            continue

        # Parse path: /api/actions/<package>/<action>/run
        path_parts = path.strip("/").split("/")

        # Must have exactly 5 parts: ["api", "actions", "<package>", "<action>", "run"]
        if (
            len(path_parts) != 5  # noqa: PLR2004
            or path_parts[0] != "api"
            or path_parts[1] != "actions"
            or path_parts[4] != "run"
        ):
            logger.warning(f"Skipping path with unexpected format: {path}")
            continue

        package_name = path_parts[2]
        action_name = path_parts[3]

        # Only process POST methods with 200 responses
        post_spec = methods.get("post")
        if not post_spec or "200" not in post_spec.get("responses", {}):
            continue

        # Convert to human-friendly names
        friendly_package_name = _to_human_friendly_name(package_name)
        friendly_action_name = _to_human_friendly_name(action_name)

        # Initialize package if it doesn't exist
        packages_dict.setdefault(friendly_package_name, [])

        # Add action to package
        packages_dict[friendly_package_name].append(friendly_action_name)

    return packages_dict


async def _process_action_packages(agent) -> list[ActionPackageDetail]:
    """Process action packages and return their details."""
    all_action_details = []

    # Group action packages by URL to avoid duplicate calls
    url_to_packages = defaultdict(list)
    for action_package in agent.action_packages:
        if action_package.url:
            url_to_packages[action_package.url].append(action_package)

    # Fetch action packages data once per unique URL
    for url, packages in url_to_packages.items():
        try:
            # Get the first package to extract api_key (they should all be the same for same URL)
            api_key = packages[0].api_key.get_secret_value() if packages[0].api_key else ""

            # Fetch action packages data from OpenAPI spec
            action_packages_data = await _fetch_action_packages_data(url, api_key)

            # Create package details directly from server response
            for pkg_name, actions in action_packages_data.items():
                package_actions = [ActionDetail(name=action) for action in actions]

                # Only create package if it has actions
                if package_actions:
                    action_package_details = ActionPackageDetail(
                        name=pkg_name,
                        actions=package_actions,
                        version="1.0.0",
                        status="online",
                    )
                    all_action_details.append(action_package_details)

        except Exception as e:
            logger.error(f"Error processing action packages from {url}: {e}")
            for package in packages:
                action_package_details = ActionPackageDetail(
                    name=package.name,
                    actions=[],
                    version=package.version,
                    status="offline",
                )
                all_action_details.append(action_package_details)

    return all_action_details


async def _process_mcp_servers(agent) -> list[MCPServerDetail]:
    """Process MCP servers and return their details."""
    all_mcp_server_details = []

    for mcp_server in agent.mcp_servers:
        try:
            tool_defs = await mcp_server.to_tool_definitions()
            allowed_actions = [MCPToolDetail(name=tool_def.name) for tool_def in tool_defs]
            mcp_server_details = MCPServerDetail(
                name=mcp_server.name,
                actions=allowed_actions,
                status="online",
            )
        except Exception as e:
            logger.error(f"Error getting tool definitions for MCP server {mcp_server.name}: {e}")
            mcp_server_details = MCPServerDetail(
                name=mcp_server.name,
                actions=[],
                status="offline",
            )
        all_mcp_server_details.append(mcp_server_details)

    return all_mcp_server_details


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
    return [
        AgentCompat.from_agent(a, reveal_sensitive=True)
        for a in await storage.list_agents(user.user_id)
    ]


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
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id, agent_id=aid)
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
) -> AgentCompat:
    agent = UpsertAgentPayload.to_agent(payload, user_id=user.user_id, agent_id=aid)
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
    await storage.delete_agent(user.user_id, aid)


@router.post("/package", response_model=AgentCompat)
async def create_agent_from_package(
    user: AuthedUser,
    payload: AgentPackagePayload,
    storage: StorageDependency,
) -> AgentCompat:
    aid = str(uuid.uuid4())
    return await create_or_update_agent_from_package(
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
    return await create_or_update_agent_from_package(
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

    action_packages = await _process_action_packages(agent)
    mcp_servers = await _process_mcp_servers(agent)

    return AgentDetails(
        runbook=agent.runbook_structured.raw_text,
        action_packages=action_packages,
        mcp_servers=mcp_servers,
    )
