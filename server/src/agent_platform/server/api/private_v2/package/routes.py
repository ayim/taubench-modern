import uuid

from fastapi import APIRouter, Request
from structlog import get_logger

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.hash.agent_package_hash import calculate_agent_package_hash
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.agent_package.metadata.generate_metadata import AgentMetadataGenerator
from agent_platform.core.agent_package.read import read_question_groups  # noqa: F401
from agent_platform.core.agent_package.utils import read_package_bytes
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.status_response import StatusError, StatusResponse
from agent_platform.core.payloads import AgentPackagePayload, UpsertAgentPayload
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.core.payloads.agent_package_inspection import (
    AgentPackageInspectionResponse,
    UploadedPackageInfo,
)
from agent_platform.server.api.dependencies import AgentQuotaCheck, StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.api.private_v2.package.content_handler import (
    convert_binary_to_base64,
    create_binary_zip_metadata,
    create_binary_zip_openapi_extra,
    parse_request_payload_contents,
)
from agent_platform.server.api.private_v2.package.upserts import upsert_agent_from_package
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache  # noqa: F401

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
    validated_payload, zip_content = await parse_request_payload_contents(
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
    validated_payload, zip_content = await parse_request_payload_contents(
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
        validated_payload, zip_content = await parse_request_payload_contents(
            request=request,
            payload_model=AgentPackagePayload,
        )

        # @TODO:
        # Remove when we are able to produce AgentPackageHandler directly
        # in parse_request_payload_contents.
        package_bytes = zip_content or (
            await read_package_bytes(
                path=None,
                url=validated_payload.agent_package_url,
                package_base64=validated_payload.agent_package_base64,
            )
        )

        with await AgentPackageHandler.from_bytes(package_bytes) as handler:
            # Calculate the hash
            calculation_result = await calculate_agent_package_hash(handler)

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
) -> StatusResponse[AgentPackageInspectionResponse]:
    try:
        # Handle both JSON and binary ZIP content types
        validated_payload, zip_content = await parse_request_payload_contents(
            request=request,
            payload_model=AgentPackagePayload,
        )

        # @TODO:
        # Remove when we are able to produce AgentPackageHandler directly
        # in parse_request_payload_contents.
        package_bytes = zip_content or (
            await read_package_bytes(
                path=None,
                url=validated_payload.agent_package_url,
                package_base64=validated_payload.agent_package_base64,
            )
        )

        with await AgentPackageHandler.from_bytes(package_bytes) as handler:
            metadata = await handler.read_metadata()

        # Build uploaded package info if binary ZIP was uploaded
        uploaded_package = None
        if zip_content:
            file_metadata = create_binary_zip_metadata(zip_content)
            pkg_info = file_metadata["binary_package"]
            uploaded_package = UploadedPackageInfo(
                content_type=pkg_info.get("content_type", "application/zip"),
                size=pkg_info.get("size", 0),
                format=pkg_info.get("format", "zip"),
            )

        response = AgentPackageInspectionResponse.from_metadata(metadata, uploaded_package)
        return StatusResponse.success(response)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to inspect agent package")
        return StatusResponse.failure([StatusError.from_message(f"Failed to inspect package: {e}", code="unexpected")])


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
        validated_payload, zip_content = await parse_request_payload_contents(
            request=request,
            payload_model=ActionPackagePayload,
        )

        # @TODO:
        # Remove when we are able to produce AgentPackageHandler directly
        # in parse_request_payload_contents.
        package_bytes = zip_content or (
            await read_package_bytes(
                path=None,
                url=validated_payload.action_package_url,
                package_base64=validated_payload.action_package_base64,
            )
        )

        with await ActionPackageHandler.from_bytes(package_bytes) as handler:
            metadata = await handler.read_metadata()

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
        return StatusResponse.failure([StatusError.from_message(f"Failed to inspect package: {e}", code="unexpected")])


#### CREATE ENDPOINT


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
) -> StatusResponse[dict]:
    raise NotImplementedError("Not implemented")


#### READ ENDPOINT


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
) -> StatusResponse[dict]:
    raise NotImplementedError("Not implemented")


#### BUILD ENDPOINT


@router.post(
    "/build",
    summary="Builds an Agent Package.",
    description="Builds an Agent Package from zipped Agent Project. Accepts binary ZIP files.",
)
async def build_agent_package(
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
) -> StatusResponse[dict]:
    raise NotImplementedError("Not implemented")


#### METADATA ENDPOINT


@router.post(
    "/metadata",
    summary="Generate agent package metadata",
    description="Generate agent package metadata. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def generate_agent_package_metadata(
    request: Request,
) -> StatusResponse[AgentPackageMetadata]:
    try:
        # Handle both JSON and binary ZIP content types
        logger.debug("Parsing request payload contents...")
        validated_payload, zip_content = await parse_request_payload_contents(
            request=request,
            payload_model=AgentPackagePayload,
        )

        # @TODO:
        # Remove when we are able to produce AgentPackageHandler directly
        # in parse_request_payload_contents.
        logger.debug("Reading package bytes...")
        package_bytes = zip_content or (
            await read_package_bytes(
                path=None,
                url=validated_payload.agent_package_url,
                package_base64=validated_payload.agent_package_base64,
            )
        )

        with await AgentPackageHandler.from_bytes(package_bytes) as handler:
            logger.debug("Generating agent package metadata...")
            generator = AgentMetadataGenerator(handler)
            metadata = await generator.generate()

        logger.debug("Metadata generated successfully")
        return StatusResponse.success(metadata)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to generate agent package metadata")
        return StatusResponse.failure(
            [StatusError.from_message(f"Failed to generate metadata: {e}", code="unexpected")]
        )
