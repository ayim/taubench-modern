import uuid

from fastapi import APIRouter, HTTPException, Request, status
from structlog import get_logger

from agent_platform.core.agent_package.hash.agent_package_hash import calculate_agent_package_hash
from agent_platform.core.agent_package.metadata.action_metadata import (
    ActionPackageMetadata,
)
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.agent_package.metadata.read_metadata import (
    read_action_package_metadata,
    read_agent_package_metadata,
)
from agent_platform.core.agent_package.upsert_from_package import upsert_agent_from_package
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.status_response import StatusError, StatusResponse
from agent_platform.core.payloads import AgentPackagePayload, UpsertAgentPayload
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.server.api.dependencies import AgentQuotaCheck, StorageDependency
from agent_platform.server.api.package_content_handler import (
    convert_binary_to_base64,
    create_binary_zip_metadata,
    create_binary_zip_openapi_extra,
    handle_json_or_binary_zip,
)
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.auth import AuthedUser

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
            mcp_server_ids=validated_payload.mcp_server_ids,
            langsmith=validated_payload.langsmith,
            platform_params_ids=validated_payload.platform_params_ids,
            selected_tools=validated_payload.selected_tools,
        )

        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(zip_content)
        logger.info(
            "Binary ZIP uploaded for agent deployment",
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

    aid = str(uuid.uuid4())
    result = await upsert_agent_from_package(
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
            mcp_server_ids=validated_payload.mcp_server_ids,
            langsmith=validated_payload.langsmith,
            platform_params_ids=validated_payload.platform_params_ids,
            selected_tools=validated_payload.selected_tools,
        )

        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(zip_content)
        logger.info(
            "Binary ZIP uploaded for agent update",
            agent_id=aid,
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

    result = await upsert_agent_from_package(
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
async def calculate_agent_package_environment_hash(
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
                mcp_server_ids=validated_payload.mcp_server_ids,
                langsmith=validated_payload.langsmith,
                platform_params_ids=validated_payload.platform_params_ids,
            )

        # Calculate the hash
        calculation_result = await calculate_agent_package_hash(
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
    payload: ActionPackagePayload,  # Unused parameter, added to fix OpenAPI spec generation
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


@router.post(
    "/create",
    response_model=AgentCompat,
    summary="Create new Agent Package",
    description="Create a new Agent Package.",
)
async def create_agent_package(
    payload: UpsertAgentPayload,
    user: AuthedUser,
    storage: StorageDependency,
    _quota: AgentQuotaCheck,
):
    raise NotImplementedError("Not implemented")


@router.post(
    "/read",
    response_model=AgentCompat,
    summary="Read Agent data from an Agent Package",
    description="Read Agent data from an Agent Package. Accepts binary ZIP files.",
)
async def read_agent_package(
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
):
    raise NotImplementedError("Not implemented")


@router.post(
    "/build",
    summary="Builds an Agent Package.",
    description="Builds an Agent Package from zipped Agent Project. Accepts binary ZIP files.",
)
async def build_agent_package(
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
):
    raise NotImplementedError("Not implemented")


# ===============================
# HELPER FUNCTIONS
# ===============================


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

    return await read_agent_package_metadata(
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

    return await read_action_package_metadata(
        path=None,  # No local path option here: either URL or base64
        url=payload.action_package_url,
        package_base64=payload.action_package_base64,
    )
