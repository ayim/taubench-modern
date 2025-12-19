import uuid

from fastapi import APIRouter, File, Request, UploadFile
from structlog import get_logger

from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.hash.agent_package_hash import calculate_agent_package_hash
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.agent_package.metadata.generate_metadata import AgentMetadataGenerator
from agent_platform.core.agent_package.read import ReadAgentPackageResult
from agent_platform.core.agent_package.read import read_agent_package as core_read_agent_package
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.status_response import StatusError, StatusResponse
from agent_platform.core.payloads import UpsertAgentPayload
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.core.payloads.agent_package_inspection import (
    AgentPackageInspectionResponse,
    UploadedPackageInfo,
)
from agent_platform.server.api.dependencies import AgentQuotaCheck, StorageDependency
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.server.api.private_v2.package.request_content_handler import (
    create_binary_zip_metadata,
    create_binary_zip_openapi_extra,
    iter_upload_file_chunks,
    parse_action_package_payload,
    parse_agent_package_payload,
)
from agent_platform.server.api.private_v2.package.upserts import upsert_agent_from_package
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


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
    validated_payload, handler = await parse_agent_package_payload(request=request)

    with handler:
        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(handler.get_spooled_file_size())
        logger.info(
            "Binary ZIP uploaded for agent deployment",
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

        aid = str(uuid.uuid4())
        result = await upsert_agent_from_package(
            user=user, aid=aid, payload=validated_payload, storage=storage, handler=handler
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
    validated_payload, handler = await parse_agent_package_payload(request=request)

    with handler:
        # Log binary ZIP metadata for tracking
        file_metadata = create_binary_zip_metadata(handler.get_spooled_file_size())
        logger.info(
            "Binary ZIP uploaded for agent deployment",
            agent_name=validated_payload.name,
            file_metadata=file_metadata,
        )

        result = await upsert_agent_from_package(
            user=user, aid=aid, payload=validated_payload, storage=storage, handler=handler
        )

        return result


@router.post(
    "/environment-hash/agent",
    summary="Calculate agent package environment hash",
    description="Calculate agent package environment hash. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def calculate_agent_package_environment_hash(
    user: AuthedUser,
    request: Request,
) -> StatusResponse[dict]:
    try:
        # Handle both JSON and binary ZIP content types
        _, handler = await parse_agent_package_payload(request=request)

        with handler:
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


@router.post(
    "/inspect/agent",
    summary="Inspect agent package",
    description="Inspect agent package metadata. Accepts JSON and binary ZIP files.",
    openapi_extra=create_binary_zip_openapi_extra("AgentPackagePayload"),
)
async def inspect_agent_from_package(
    user: AuthedUser,
    request: Request,
) -> StatusResponse[AgentPackageInspectionResponse]:
    try:
        # Handle both JSON and binary ZIP content types
        _, handler = await parse_agent_package_payload(request=request)

        with handler:
            metadata = await handler.read_metadata()

            # Build uploaded package info
            file_metadata = create_binary_zip_metadata(handler.get_spooled_file_size())
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
    user: AuthedUser,
    request: Request,
    payload: ActionPackagePayload,  # Unused parameter, added to fix OpenAPI spec generation
) -> StatusResponse[dict]:
    try:
        # Handle both JSON and binary ZIP content types
        _, handler = await parse_action_package_payload(request=request)

        with handler:
            metadata = await handler.read_metadata()

            result = metadata.model_dump()

            # Add file metadata to the response
            file_metadata = create_binary_zip_metadata(handler.get_spooled_file_size())
            result["uploaded_package"] = file_metadata["binary_package"]

            return StatusResponse.success(result)
    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to inspect action package")
        return StatusResponse.failure([StatusError.from_message(f"Failed to inspect package: {e}", code="unexpected")])


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


@router.post(
    "/read",
    response_model=ReadAgentPackageResult,
    summary="Read Agent data from an Agent Package",
    description="Read Agent data from an Agent Package. Accepts binary ZIP files.",
)
async def read_agent_package(
    user: AuthedUser,
    package_zip_file: UploadFile = File(..., description="Agent Package ZIP file"),  # noqa: B008
) -> ReadAgentPackageResult:
    with await AgentPackageHandler.from_stream(iter_upload_file_chunks(package_zip_file)) as handler:
        return await core_read_agent_package(handler)


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
        # Handle both JSON and binary ZIP content types
        _, handler = await parse_agent_package_payload(request=request)

        with handler:
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
