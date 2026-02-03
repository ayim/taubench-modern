import uuid

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from structlog import get_logger

from agent_platform.core.agent_package.build import AgentPackageBuilder
from agent_platform.core.agent_package.create import create_agent_project_zip, expand_action_packages_from_uris
from agent_platform.core.agent_package.diff import AgentDiffResult, calculate_agent_diff
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.hash.agent_package_hash import calculate_agent_package_hash
from agent_platform.core.agent_package.metadata.agent_metadata import (
    AgentPackageMetadata,
)
from agent_platform.core.agent_package.metadata.agent_metadata_generator import AgentMetadataGenerator
from agent_platform.core.agent_package.read import ReadAgentPackageResult
from agent_platform.core.agent_package.read import read_agent_package as core_read_agent_package
from agent_platform.core.agent_package.spec import SpecActionPackageType
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
from agent_platform.server.api.private_v2.package.utils import unwrap_semantic_data_model_dicts
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

        aid = str(uuid.uuid4())

        logger.info(
            "Binary ZIP uploaded for agent deployment",
            agent_id=aid,
            file_metadata=file_metadata,
        )

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
            agent_id=aid,
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

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.core.semantic_data_model.types import SemanticDataModel

    # Check if the agent exists
    agent = await storage.get_agent(user.user_id, payload.agent_id)
    if not agent:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message="Agent not found")

    # Get semantic data models associated with this agent (if any)
    semantic_data_models: list[SemanticDataModel] = []
    try:
        sdm_dicts = await storage.get_agent_semantic_data_models(payload.agent_id)
        semantic_data_models = unwrap_semantic_data_model_dicts(sdm_dicts)
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
    action_package_type: SpecActionPackageType | None = Form(  # noqa: B008
        None, description="Action package type to include in the build: zip or folder"
    ),
) -> Response:
    """Build an agent package from a zipped agent project.

    The Agent Project Zip File is a zip file containing a compressed Agent Project Folder.

    Args:
        user: The user building the agent package.
        storage: The storage dependency.
        project_package_zip: The zip file containing the compressed Agent Project Folder.
        action_package_type: Optional action package type to use ("zip" or "folder").

    Returns:
        A Response containing the agent package zip file.
    """
    if action_package_type is None:
        action_package_type = "zip"

    if action_package_type not in ("zip", "folder"):
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="action_package_type must be 'zip' or 'folder'",
        )

    # Read the uploaded zip file contents
    with await AgentPackageHandler.from_stream(iter_upload_file_chunks(project_package_zip)) as handler:
        builder = AgentPackageBuilder(handler)
        headers = {"Content-Disposition": 'attachment; filename="agent_package.zip"'}
        return StreamingResponse(
            await builder.build(action_package_type=action_package_type),
            media_type="application/zip",
            headers=headers,
        )


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


@router.post(
    "/diff",
    summary="Compare agent package with deployed agent",
    description="Compare an agent package with a deployed agent. Accepts binary ZIP files.",
)
async def diff_agent_package(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str,
    agent_package_zip: UploadFile = File(..., description="Agent Package ZIP file"),  # noqa: B008
) -> StatusResponse[AgentDiffResult]:
    """Compare an agent package with a deployed agent.

    Args:
        user: The authenticated user.
        storage: The storage dependency.
        agent_id: The ID of the deployed agent to compare against.
        agent_package_zip: The zip file containing the Agent Package.

    Returns:
        A StatusResponse containing the AgentDiffResult with all differences found.
    """

    from agent_platform.core.semantic_data_model.types import SemanticDataModel

    try:
        # Create handler from the uploaded zip file
        with await AgentPackageHandler.from_stream(iter_upload_file_chunks(agent_package_zip)) as handler:
            # Get the deployed agent from storage
            deployed_agent = await storage.get_agent(user.user_id, agent_id)

            # Get deployed semantic data models
            deployed_sdms: list[SemanticDataModel] = []
            try:
                sdm_dicts = await storage.get_agent_semantic_data_models(agent_id)
                deployed_sdms = unwrap_semantic_data_model_dicts(sdm_dicts)
            except Exception as e:
                logger.warning("Failed to fetch semantic data models for diff", agent_id=agent_id, error=str(e))

            # Read the spec agent from the package
            spec_agent = await handler.get_spec_agent()

            # Read question groups from conversation guide file
            spec_question_groups = await handler.read_conversation_guide()

            # Read runbook content from the package
            spec_runbook = await handler.read_runbook()

            # Read semantic data models from the package
            spec_semantic_data_models = await handler.read_all_semantic_data_models()

            # Calculate diff
            diff_result = await calculate_agent_diff(
                deployed_agent=deployed_agent,
                deployed_sdms=deployed_sdms,
                spec_agent=spec_agent,
                spec_question_groups=spec_question_groups,
                spec_runbook=spec_runbook,
                spec_sdms=spec_semantic_data_models,
            )

            return StatusResponse.success(diff_result)

    except PlatformError as e:
        return StatusResponse.failure([StatusError.from_platform_error(e)])
    except Exception as e:
        logger.exception("Failed to compare agent package with deployed agent")
        return StatusResponse.failure([StatusError.from_message(f"Failed to compare packages: {e}", code="unexpected")])


@router.post(
    "/patch",
    response_class=Response,
    summary="Create a patch for an agent project from an agent package",
    description=(
        "Compares the incoming Agent Package with the current Agent state and returns a ZIP "
        "containing only the files that need to be updated. The client can unzip the returned "
        "patch into the Agent Project to apply the changes."
    ),
)
async def patch_agent_project(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str,
    agent_package_zip: UploadFile = File(..., description="Agent Package ZIP file"),  # noqa: B008
    action_packages_uris: str | None = Form(None, description="JSON array of action package URIs"),
) -> Response:
    """Create a patch for an agent project from an agent package.

    Compares the incoming Agent Package (current local state) with the deployed Agent state
    and returns a ZIP containing only the files that differ. This enables partial updates
    where only changed files are overwritten instead of replacing the entire package.
    Returns 204 No Content if there are no changes to patch.

    Args:
        user: The authenticated user.
        storage: The storage dependency.
        agent_id: The ID of the agent to compare against.
        agent_package_zip: The zip file containing the Agent Package (current local state).
        action_packages_uris: Optional JSON string containing array of action package URIs.

    Returns:
        A Response containing the patch zip file with only the changed files.
    """
    import json

    from agent_platform.core.agent_package.patch import create_agent_project_patch
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode
    from agent_platform.core.semantic_data_model.types import SemanticDataModel

    # Parse action_packages_uris from JSON string
    parsed_action_packages_uris: list[str] = []
    if action_packages_uris:
        try:
            parsed = json.loads(action_packages_uris)
            if isinstance(parsed, list):
                parsed_action_packages_uris = [uri for uri in parsed if isinstance(uri, str)]
        except json.JSONDecodeError as e:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Invalid JSON in action_packages_uris: {e}",
            ) from e

    # Check if the agent exists
    agent = await storage.get_agent(user.user_id, agent_id)
    if not agent:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message="Agent not found")

    # Get semantic data models associated with this agent (if any)
    semantic_data_models: list[SemanticDataModel] = []
    try:
        sdm_dicts = await storage.get_agent_semantic_data_models(agent_id)
        semantic_data_models = unwrap_semantic_data_model_dicts(sdm_dicts)
    except Exception as e:
        logger.warning("Failed to fetch semantic data models", agent_id=agent_id, error=str(e))

    # Create handler from the uploaded zip file (current local state)
    with await AgentPackageHandler.from_stream(iter_upload_file_chunks(agent_package_zip)) as agent_package_handler:
        # Create the patch by comparing incoming package with deployed state
        patch_stream = await create_agent_project_patch(
            deployed_agent=agent,
            deployed_sdms=semantic_data_models,
            action_packages_uris=parsed_action_packages_uris,
            agent_package_handler=agent_package_handler,
        )

        # Return 204 No Content - if there are no changes
        if patch_stream is None:
            return Response(status_code=204)

        # Return 200 OK - with the patch zip file
        headers = {"Content-Disposition": 'attachment; filename="agent_patch.zip"'}
        return StreamingResponse(
            patch_stream,
            media_type="application/zip",
            headers=headers,
        )
