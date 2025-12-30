import uuid

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from structlog import get_logger

from agent_platform.core.agent_package.build import AgentPackageBuilder
from agent_platform.core.agent_package.create import create_agent_project_zip, expand_action_packages_from_uris
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.hash.agent_package_hash import calculate_agent_package_hash
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.agent_package.metadata.agent_metadata_generator import AgentMetadataGenerator
from agent_platform.core.agent_package.read import ReadAgentPackageResult
from agent_platform.core.agent_package.read import read_agent_package as core_read_agent_package
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.status_response import StatusError, StatusResponse
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.core.payloads.agent_package_create import AgentPackageCreatePayload
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
    response_class=Response,
    summary="Create new Agent Project Package from existing Agent",
    description=(
        "Create a new Agent Project Package based on Agent ID from an existing Agent in Agent Server. "
        "Response is the Agent Project packaged as a zip file."
        "The Agent Project Zip File is a zip file containing the agent project as a Folder."
    ),
)
async def create_agent_project_zip_package(
    user: AuthedUser,
    storage: StorageDependency,
    payload: AgentPackageCreatePayload,
) -> Response:
    """
    Create an agent project zip file from an existing agent.
    The Agent Project Zip File is a zip file containing the agent project as a Folder.

    Args:
        user: The user creating the agent project zip package.
        storage: The storage dependency.
        payload: The payload containing the agent ID and action packages URIs.

    Returns:
        A Response containing the agent project zip file.
        The Agent Project Zip File is a zip file containing the agent project as a Folder.
    """
    from typing import cast

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    # Check if the agent exists
    agent = await storage.get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message="Agent not found")

    # Get semantic data models associated with this agent (if any)
    semantic_data_models: list[SemanticDataModel] = []
    try:
        sdm_dicts = await storage.get_agent_semantic_data_models(payload.agent_id)
        # Cast the dicts to SemanticDataModel TypedDicts
        semantic_data_models = cast(list[SemanticDataModel], sdm_dicts)
    except Exception as e:
        logger.warning("Failed to fetch semantic data models", agent_id=payload.agent_id, error=str(e))

    # Expand action packages from the provided URIs
    action_packages_map = await expand_action_packages_from_uris(agent, payload.action_packages_uris)

    # Prepare the response
    headers = {"Content-Disposition": 'attachment; filename="agent_package.zip"'}
    return StreamingResponse(
        await create_agent_project_zip(agent, semantic_data_models, action_packages_map),
        media_type="application/zip",
        headers=headers,
    )


@router.post(
    "/build",
    response_class=Response,
    summary="Builds an Agent Package from a zipped Agent Project",
    description="Builds an Agent Package from a zipped Agent Project. "
    "Accepts a zip file containing a compressed Agent Project Folder.",
)
async def build_agent_package(
    user: AuthedUser,
    storage: StorageDependency,
    project_package_zip: UploadFile = File(..., description="Agent Project Package ZIP file"),  # noqa: B008
) -> Response:
    """Build an agent package from a zipped agent project.

    The Agent Project Zip File is a zip file containing a compressed Agent Project Folder.

    Args:
        user: The user building the agent package.
        storage: The storage dependency.
        project_package_zip: The zip file containing the compressed Agent Project Folder.

    Returns:
        A Response containing the agent package zip file.
    """
    # Read the uploaded zip file contents
    project_zip_bytes = await project_package_zip.read()

    with await AgentPackageHandler.from_bytes(project_zip_bytes) as handler:
        builder = AgentPackageBuilder(handler)
        headers = {"Content-Disposition": 'attachment; filename="agent_package.zip"'}
        return StreamingResponse(await builder.build(), media_type="application/zip", headers=headers)


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
