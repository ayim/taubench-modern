import json
import uuid
from collections.abc import Mapping
from typing import Any

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
from agent_platform.server.storage.errors import AgentNotFoundError

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
                mcp_server_ids=validated_payload.mcp_server_ids,
                langsmith=validated_payload.langsmith,
                platform_params_ids=validated_payload.platform_params_ids,
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


# ===============================
# HELPER FUNCTIONS
# ===============================


async def create_or_update_agent_from_package(  # noqa: C901, PLR0912, PLR0915
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
    await _import_semantic_data_models(
        agent_id=aid,
        sdms=agent_package.semantic_data_models,
        storage=storage,
    )

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


# ===============================
# SDM IMPORT HELPER FUNCTIONS
# ===============================


def _strip_environment_specific_fields(sdm: dict) -> dict:
    """
    Remove environment-specific fields from SDM before storing.

    Environment-specific fields that are stripped:
    - data_connection_id in base_table (environment-specific UUID)
    - data_connection_name in base_table (resolved to ID during import)
    - file references (thread_id, file_ref) (environment-specific)

    Preserved fields (portable across environments):
    - database and schema in base_table (part of the SDM definition)
    - table name (part of the SDM definition)
    """
    import copy

    sdm_clean = copy.deepcopy(sdm)

    # Remove only environment-specific IDs and names (keep database/schema)
    for table in sdm_clean.get("tables", []):
        if "base_table" in table:
            table["base_table"].pop("data_connection_id", None)
            table["base_table"].pop("data_connection_name", None)
            # Note: database and schema are NOT stripped - they are part of the SDM definition

        # Remove file references
        if "file" in table:
            table.pop("file", None)

    return sdm_clean


def _normalize_sdm_for_comparison(sdm: dict) -> str:
    """
    Normalize SDM for comparison by converting to sorted JSON string.

    This ensures consistent comparison regardless of dict ordering.
    """
    import json

    # Strip environment fields first
    normalized = _strip_environment_specific_fields(sdm)

    # Convert to sorted JSON string for consistent comparison
    return json.dumps(normalized, sort_keys=True)


def _find_matching_sdm(
    new_sdm: dict,
    existing_sdms: list[dict],
) -> str | None:
    """
    Find existing SDM that matches the new SDM being imported.

    Matching criteria:
    1. Same name (case-insensitive)
    2. Same content (after normalizing both)

    Args:
        new_sdm: New SDM content from package
        existing_sdms: List of existing SDMs in format [{sdm_id: sdm_content}, ...]

    Returns:
        existing SDM ID if match found, None otherwise
    """
    new_name = new_sdm.get("name", "").lower()
    new_normalized = _normalize_sdm_for_comparison(new_sdm)

    for existing_sdm_entry in existing_sdms:
        # existing_sdm_entry format: {sdm_id: sdm_content}
        for sdm_id, existing_sdm in existing_sdm_entry.items():
            existing_name = existing_sdm.get("name", "").lower()

            # Check name match
            if new_name == existing_name:
                existing_normalized = _normalize_sdm_for_comparison(existing_sdm)

                # Check content match
                if new_normalized == existing_normalized:
                    logger.info(
                        f"Found matching SDM: {sdm_id} for '{new_name}'",
                        sdm_id=sdm_id,
                        sdm_name=new_name,
                    )
                    return sdm_id  # Perfect match - reuse this SDM

    return None  # No match found - need to create new


async def _resolve_data_connection_names(
    sdm_content: dict,
    storage: StorageDependency,
) -> dict:
    """
    Resolve data_connection_name to data_connection_id in SDM.

    If data_connection_name is present but data_connection_id is not,
    attempts to find the connection by name (case-insensitive).

    Args:
        sdm_content: SDM content from package
        storage: Storage dependency

    Returns:
        Updated SDM content with data_connection_id resolved (if found)
    """
    import copy

    sdm = copy.deepcopy(sdm_content)

    for table in sdm.get("tables", []):
        base_table = table.get("base_table", {})

        # If name is present but ID is not
        if "data_connection_name" in base_table and not base_table.get("data_connection_id"):
            name = base_table["data_connection_name"]

            # Try to find connection by name
            connection = await storage.get_data_connection_by_name(name)

            if connection:
                base_table["data_connection_id"] = connection.id
                logger.info(
                    f"Resolved data connection '{name}' → {connection.id}",
                    connection_name=name,
                    connection_id=connection.id,
                )
            else:
                logger.warning(
                    f"Data connection '{name}' not found. SDM will need manual configuration.",
                    connection_name=name,
                )

    return sdm


async def _import_semantic_data_models(  # noqa: C901
    agent_id: str,
    sdms: Mapping[str, dict[str, Any]] | None,
    storage: StorageDependency,
) -> None:
    """
    Import semantic data models from agent package with deduplication.

    Mode: Additive - preserves existing SDMs and adds new ones.

    Args:
        agent_id: ID of the agent to link SDMs to
        sdms: Dictionary of SDM filename to content (or None if no SDMs)
        storage: Storage dependency
    """
    if not sdms:
        logger.info(f"No SDMs to import for agent {agent_id}")
        return

    logger.info(f"Importing {len(sdms)} SDMs for agent {agent_id}", agent_id=agent_id)

    # Get existing SDMs for this agent
    existing_sdms = await storage.get_agent_semantic_data_models(agent_id)

    # Track which SDM IDs to link (existing + new)
    sdm_ids_to_link = []

    # Keep existing SDM IDs (additive mode)
    existing_ids = [next(iter(sdm_entry.keys())) for sdm_entry in existing_sdms]
    sdm_ids_to_link.extend(existing_ids)
    logger.info(f"Keeping {len(existing_ids)} existing SDMs", count=len(existing_ids))

    # Process each SDM from package
    for filename, sdm_content in sdms.items():
        # Resolve data connection names to IDs (if possible)
        sdm_resolved = await _resolve_data_connection_names(sdm_content, storage)

        # Strip environment-specific fields for comparison only
        sdm_for_comparison = _strip_environment_specific_fields(sdm_resolved)

        # Check for match
        matching_id = _find_matching_sdm(sdm_for_comparison, existing_sdms)

        if matching_id:
            logger.info(
                f"Reusing existing SDM {matching_id} for {filename}",
                sdm_id=matching_id,
                sdm_filename=filename,
            )
            # Don't add to list if already there (from additive mode)
            if matching_id not in sdm_ids_to_link:
                sdm_ids_to_link.append(matching_id)
        else:
            # Prepare SDM for storage: keep data_connection_id, remove data_connection_name
            import copy

            sdm_for_storage = copy.deepcopy(sdm_resolved)
            for table in sdm_for_storage.get("tables", []):
                if "base_table" in table:
                    # Remove data_connection_name (was only needed for import resolution)
                    table["base_table"].pop("data_connection_name", None)
                    # Keep data_connection_id (needed for querying)

            # Extract data connection IDs from resolved SDM (for junction table)
            data_connection_ids = []
            for table in sdm_resolved.get("tables", []):
                base_table = table.get("base_table", {})
                if "data_connection_id" in base_table:
                    dc_id = base_table["data_connection_id"]
                    if dc_id and dc_id not in data_connection_ids:
                        data_connection_ids.append(dc_id)

            # Create new SDM
            # Note: We store sdm_for_storage which has data_connection_id (for querying)
            # The junction table also stores the IDs for reference
            new_id = await storage.set_semantic_data_model(
                semantic_data_model_id=None,
                semantic_model=sdm_for_storage,
                data_connection_ids=data_connection_ids,
                file_references=[],
            )
            logger.info(
                f"Created new SDM {new_id} for {filename}",
                sdm_id=new_id,
                sdm_filename=filename,
                sdm_name=sdm_for_storage.get("name", ""),
                data_connection_count=len(data_connection_ids),
            )
            sdm_ids_to_link.append(new_id)

    # Link all SDMs to agent
    if sdm_ids_to_link:
        await storage.set_agent_semantic_data_models(agent_id, sdm_ids_to_link)
        logger.info(
            f"Linked {len(sdm_ids_to_link)} SDMs to agent {agent_id}",
            agent_id=agent_id,
            sdm_count=len(sdm_ids_to_link),
        )
