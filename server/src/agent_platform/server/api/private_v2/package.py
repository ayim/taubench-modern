import uuid

from fastapi import APIRouter, HTTPException, Request, status
from structlog import get_logger

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import AgentArchitecture
from agent_platform.core.agent_spec.extract_spec import extract_and_validate_agent_package
from agent_platform.core.agent_spec.package.action_metadata import (
    ActionPackageMetadata,
    extract_action_package_metadata,
)
from agent_platform.core.agent_spec.package.agent_hash import calculate_agent_hash
from agent_platform.core.agent_spec.package.agent_metadata import (
    AgentPackageMetadata,
    extract_agent_package_metadata,
)
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.status_response import StatusError, StatusResponse
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.payloads import AgentPackagePayload, UpsertAgentPayload
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.core.payloads.agent_package import (
    AgentPackagePayloadActionServer,
    AgentPackagePayloadLangsmith,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import AgentQuotaCheck, StorageDependency
from agent_platform.server.api.package_content_handler import (
    convert_binary_to_base64,
    create_binary_zip_metadata,
    create_binary_zip_openapi_extra,
    handle_json_or_binary_zip,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache

router = APIRouter()
logger = get_logger(__name__)


# ===============================
# ROUTES
# ===============================

#### DEPLOY ENDPOINT


@router.post(
    "/deploy/agent",
    response_model=AgentCompat,
    summary="Deploy agent from package",
    description="Deploy an agent from a package. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def deploy_agent_from_package(
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
    _: AgentQuotaCheck = None,
) -> AgentCompat:
    # Handle both JSON and binary ZIP content types
    validated_payload, zip_content = await handle_json_or_binary_zip(
        request=request,
        payload_model=AgentPackagePayload,
    )

    # If binary ZIP was uploaded, convert it to base64 and set it in the payload
    if zip_content:
        package_base64 = await convert_binary_to_base64(zip_content)
        # Create a new payload with the uploaded file as base64
        validated_payload = AgentPackagePayload(
            name=validated_payload.name,
            description=validated_payload.description,
            public=validated_payload.public,
            agent_package_url=None,  # Clear URL since we have binary content
            agent_package_base64=package_base64,  # Set base64 from binary ZIP
            model=validated_payload.model,
            action_servers=validated_payload.action_servers,
            mcp_servers=validated_payload.mcp_servers,
            langsmith=validated_payload.langsmith,
        )

        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(zip_content)
        logger.info(
            "Binary ZIP uploaded for agent deployment",
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

    aid = str(uuid.uuid4())
    result = await create_or_update_agent_from_package(
        user=user,
        aid=aid,
        payload=validated_payload,
        storage=storage,
    )

    return result


@router.put(
    "/deploy/agent/{aid}",
    response_model=AgentCompat,
    summary="Update agent from package",
    description="Update an existing agent from a package. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def update_agent_from_package(
    user: AuthedUser,
    aid: str,
    request: Request,
    storage: StorageDependency,
) -> AgentCompat:
    # Handle both JSON and binary ZIP content types
    validated_payload, zip_content = await handle_json_or_binary_zip(
        request=request,
        payload_model=AgentPackagePayload,
    )

    # If binary ZIP was uploaded, convert it to base64 and set it in the payload
    if zip_content:
        package_base64 = await convert_binary_to_base64(zip_content)
        # Create a new payload with the uploaded file as base64
        validated_payload = AgentPackagePayload(
            name=validated_payload.name,
            description=validated_payload.description,
            public=validated_payload.public,
            agent_package_url=None,  # Clear URL since we have binary content
            agent_package_base64=package_base64,  # Set base64 from binary ZIP
            model=validated_payload.model,
            action_servers=validated_payload.action_servers,
            mcp_servers=validated_payload.mcp_servers,
            langsmith=validated_payload.langsmith,
        )

        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(zip_content)
        logger.info(
            "Binary ZIP uploaded for agent update",
            agent_id=aid,
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

    result = await create_or_update_agent_from_package(
        user=user,
        aid=aid,
        payload=validated_payload,
        storage=storage,
    )

    return result


#### ENVIRONMENT HASH ENDPOINT


@router.post(
    "/environment-hash/agent",
    summary="Calculate agent package environment hash",
    description="Calculate agent package environment hash. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def calculate_agent_package_hash(
    request: Request,
) -> StatusResponse[dict]:
    try:
        # Handle both JSON and binary ZIP content types
        validated_payload, zip_content = await handle_json_or_binary_zip(
            request=request,
            payload_model=AgentPackagePayload,
        )

        if zip_content:
            package_base64 = await convert_binary_to_base64(zip_content)
            # Create a new payload with the uploaded file as base64
            validated_payload = AgentPackagePayload(
                name=validated_payload.name,
                description=validated_payload.description,
                public=validated_payload.public,
                agent_package_url=None,  # Clear URL since we have binary content
                agent_package_base64=package_base64,  # Set base64 from binary ZIP
                model=validated_payload.model,
                action_servers=validated_payload.action_servers,
                mcp_servers=validated_payload.mcp_servers,
                langsmith=validated_payload.langsmith,
            )

        # Calculate the hash
        calculation_result = await calculate_agent_hash(
            path=None,  # No local path option here: either URL or base64
            url=validated_payload.agent_package_url,
            package_base64=validated_payload.agent_package_base64,
        )

        return StatusResponse.success(calculation_result)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to calculate agent package hash")
        return StatusResponse.failure(
            [StatusError.from_message(f"Failed to calculate package hash: {e}", code="unexpected")]
        )


#### INSPECT ENDPOINT


@router.post(
    "/inspect/agent",
    summary="Inspect agent package",
    description="Inspect agent package metadata. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def inspect_agent_from_package(
    request: Request,
) -> StatusResponse[dict]:
    try:
        # Handle both JSON and binary ZIP content types
        validated_payload, zip_content = await handle_json_or_binary_zip(
            request=request,
            payload_model=AgentPackagePayload,
        )

        # If binary ZIP was uploaded, convert it to base64 and set it in the payload
        if zip_content:
            package_base64 = await convert_binary_to_base64(zip_content)
            # Create a new payload with the uploaded file as base64
            validated_payload = AgentPackagePayload(
                name=validated_payload.name,
                description=validated_payload.description,
                public=validated_payload.public,
                agent_package_url=None,  # Clear URL since we have binary content
                agent_package_base64=package_base64,  # Set base64 from binary ZIP
                model=validated_payload.model,
                action_servers=validated_payload.action_servers,
                mcp_servers=validated_payload.mcp_servers,
                langsmith=validated_payload.langsmith,
            )

        metadata = await inspect_agent_package(validated_payload)
        result = metadata.model_dump()

        # If binary ZIP was uploaded, add file metadata to the response
        if zip_content:
            file_metadata = create_binary_zip_metadata(zip_content)
            result["uploaded_package"] = file_metadata["binary_package"]

        return StatusResponse.success(result)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to inspect agent package")
        return StatusResponse.failure(
            [StatusError.from_message(f"Failed to inspect package: {e}", code="unexpected")]
        )


@router.post(
    "/inspect/action",
    summary="Inspect action package",
    description="Inspect action package metadata. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("ActionPackagePayload"),
)
async def inspect_action_from_package(
    request: Request,
) -> StatusResponse[dict]:
    try:
        # Handle both JSON and binary ZIP content types
        validated_payload, zip_content = await handle_json_or_binary_zip(
            request=request,
            payload_model=ActionPackagePayload,
        )

        # If binary ZIP was uploaded, convert it to base64 and set it in the payload
        if zip_content:
            package_base64 = await convert_binary_to_base64(zip_content)
            # Create a new payload with the uploaded file as base64
            validated_payload = ActionPackagePayload(
                name=validated_payload.name,
                description=validated_payload.description,
                action_package_url=None,  # Clear URL since we have binary content
                action_package_base64=package_base64,  # Set base64 from binary ZIP
            )

        metadata = await inspect_action_package(validated_payload)
        result = metadata.model_dump()

        # If binary ZIP was uploaded, add file metadata to the response
        if zip_content:
            file_metadata = create_binary_zip_metadata(zip_content)
            result["uploaded_package"] = file_metadata["binary_package"]

        return StatusResponse.success(result)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to inspect action package")
        return StatusResponse.failure(
            [StatusError.from_message(f"Failed to inspect package: {e}", code="unexpected")]
        )


# ===============================
# HELPER FUNCTIONS
# ===============================


async def create_or_update_agent_from_package(  # noqa: C901, PLR0912
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

    # Normalize and bring over langsmith config from payload (accept dict or typed)
    advanced_config = {}
    ls_obj = payload.langsmith
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
    if payload.action_servers:
        for item in payload.action_servers:
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

    # Normalize nested fields defensively if JSON deserialization left dicts
    normalized_mcp_servers = []
    for server in payload.mcp_servers:
        if isinstance(server, dict):  # type: ignore[unreachable]
            normalized_mcp_servers.append(MCPServer.model_validate(server))
        else:
            normalized_mcp_servers.append(server)

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
        runbook=agent_package.runbook_text,
        advanced_config=advanced_config,
        question_groups=agent_package.question_groups,
        agent_settings=agent_package.agent_settings or {},
        extra={
            "conversation_starter": agent_package.conversation_starter,
            "welcome_message": agent_package.welcome_message,
            "agent_settings": agent_package.agent_settings,
        },
        model=payload.model,
        agent_architecture=AgentArchitecture(
            # Doesn't matter what we were given, all legacy architectures
            # get mapped to default for v2 & v3
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        metadata={
            **agent0.get("metadata", {}),
        },
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
    ToolDefinitionCache().clear_for_agent(as_agent)
    return AgentCompat.from_agent(as_agent)


async def inspect_agent_package(
    payload: AgentPackagePayload,
) -> AgentPackageMetadata:
    # Validate that exactly one of URL or base64 is provided
    sources = [payload.agent_package_url, payload.agent_package_base64]
    non_none_sources = [s for s in sources if s is not None]

    if len(non_none_sources) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specify exactly one of 'agent_package_url' or 'agent_package_base64'",
        )

    return await extract_agent_package_metadata(
        path=None,  # No local path option here: either URL or base64
        url=payload.agent_package_url,
        package_base64=payload.agent_package_base64,
    )


async def inspect_action_package(
    payload: ActionPackagePayload,
) -> ActionPackageMetadata:
    # Validate that exactly one of URL or base64 is provided
    sources = [payload.action_package_url, payload.action_package_base64]
    non_none_sources = [s for s in sources if s is not None]

    if len(non_none_sources) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specify exactly one of 'action_package_url' or 'action_package_base64'",
        )

    return await extract_action_package_metadata(
        path=None,  # No local path option here: either URL or base64
        url=payload.action_package_url,
        package_base64=payload.action_package_base64,
    )
