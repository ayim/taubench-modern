import json
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import APIRouter, Form, HTTPException, UploadFile
from structlog import get_logger

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.mcp.mcp_types import deserialize_mcp_variables
from agent_platform.core.payloads import MCPServerResponse
from agent_platform.server.api.dependencies import MCPQuotaCheck, StorageDependency
from agent_platform.server.env_vars import SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE
from agent_platform.server.mcp_runtime import MCPRuntimeConfig, delete_deployment
from agent_platform.server.storage import (
    ConfigDecryptionError,
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
)

router = APIRouter()
logger = get_logger(__name__)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


@dataclass
class MCPRuntimeDeploymentResponse:
    """Response from MCP Runtime API deployment endpoint."""

    url: str
    status: str
    deployment_id: str


def parse_mcp_headers_from_form(headers_json: str | None) -> dict[str, str] | None:
    """Parse and validate headers from JSON string in form data.

    Args:
        headers_json: Optional JSON string containing headers

    Returns:
        Parsed headers dictionary or None if not provided

    Raises:
        HTTPException: If JSON is invalid or not a dictionary
    """
    if not headers_json:
        return None

    try:
        parsed_headers = json.loads(headers_json)
        if not isinstance(parsed_headers, dict):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Headers must be a JSON object",
            )
        return parsed_headers
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid JSON in headers field: {e}",
        ) from e


async def call_mcp_runtime_deployment_api(
    deployment_endpoint: str, file_content: bytes
) -> MCPRuntimeDeploymentResponse:
    """Call MCP Runtime API to deploy a package.

    This function is extracted to enable easier testing by allowing
    tests to mock this function without mocking the entire httpx client.

    Args:
        deployment_endpoint: Full URL to the deployment endpoint
        file_content: Binary content of the package file

    Returns:
        Parsed deployment response from MCP Runtime API

    Raises:
        Exception: Various exceptions from httpx or response parsing
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            deployment_endpoint,
            content=file_content,
            headers={"Content-Type": "application/octet-stream"},
        )
        response.raise_for_status()

        response_data = response.json()

        if not isinstance(response_data, dict):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="MCP Runtime API returned invalid response format",
            )

        deployment_url = response_data.get("url")
        deployment_status = response_data.get("status")
        returned_deployment_id = response_data.get("deploymentId")

        if not deployment_url or not deployment_status or not returned_deployment_id:
            missing_fields = []
            if not deployment_url:
                missing_fields.append("url")
            if not deployment_status:
                missing_fields.append("status")
            if not returned_deployment_id:
                missing_fields.append("deploymentId")
            missing_fields_str = ", ".join(missing_fields)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"MCP Runtime API response missing required fields: {missing_fields_str}",
            )

        return MCPRuntimeDeploymentResponse(
            url=deployment_url,
            status=deployment_status,
            deployment_id=returned_deployment_id,
        )


async def deploy_mcp_server(file: UploadFile, deployment_id: str) -> str:
    """Deploy an MCP server package and return the deployment URL.

    Uploads the package to the MCP Runtime API which deploys it and returns
    a URL where the deployed MCP server can be accessed.

    Args:
        file: The uploaded .zip file containing the MCP server package
        deployment_id: Unique identifier for this deployment

    Returns:
        Deployment URL for the MCP server

    Raises:
        HTTPException: If file validation fails or deployment fails
    """
    # Validate file extension
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must be a .zip archive",
        )

    # Validate file size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail=(f"File size ({file_size} bytes) exceeds maximum allowed size ({MAX_FILE_SIZE_BYTES} bytes)"),
        )

    # Reset file pointer for the actual upload
    await file.seek(0)

    # Get MCP Runtime API configuration from the singleton instance
    # (which has environment variables applied by ConfigurationManager)
    runtime_api_base_url = MCPRuntimeConfig.mcp_runtime_api_url

    # Construct deployment endpoint URL
    deployment_endpoint = f"{runtime_api_base_url}/api/deployments/{deployment_id}"

    logger.info(
        "Deploying MCP server package to runtime",
        filename=file.filename,
        file_size=file_size,
        deployment_id=deployment_id,
        deployment_endpoint=deployment_endpoint,
    )

    # Upload package to MCP Runtime API
    try:
        deployment_response = await call_mcp_runtime_deployment_api(deployment_endpoint, file_content)

        logger.info(
            "MCP server package deployed successfully",
            filename=file.filename,
            deployment_id=deployment_response.deployment_id,
            deployment_status=deployment_response.status,
            deployment_url=deployment_response.url,
        )

        return deployment_response.url

    except Exception as e:
        error_message = f"Failed to deploy MCP server: {e!s}"
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR

        # Extract more specific error information if available
        if isinstance(e, httpx.HTTPStatusError):
            status_code = HTTPStatus(e.response.status_code)
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict) and "error" in error_data:
                    extracted_message = error_data["error"].get("message")
                    if extracted_message:
                        error_message = f"MCP Runtime API error: {extracted_message}"
            except Exception:
                pass

        logger.error(
            "Failed to deploy MCP server package",
            error=str(e),
            deployment_id=deployment_id,
            filename=file.filename,
            deployment_endpoint=deployment_endpoint,
        )

        raise HTTPException(
            status_code=status_code,
            detail=error_message,
        ) from e


def _read_mcp_servers_config_file() -> list[MCPServer]:
    """Read and parse the MCP servers configuration file.

    Returns:
        List of MCPServer objects from the config file.
    """
    servers: list[MCPServer] = []

    config_file_path = SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE

    if not config_file_path or not isinstance(config_file_path, str):
        logger.debug("No MCP servers config file specified")
        return servers

    config_path = Path(config_file_path)
    if not config_path.exists():
        logger.warning(f"MCP servers config file not found: {config_path}")
        return servers

    try:
        with config_path.open() as f:
            try:
                config_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to parse MCP servers config file {config_path}: {e}")
                return servers

        # Parse servers from config data
        # Expected format: {"mcpServers": {"server_name": {...}, ...}}
        if not isinstance(config_data, dict) or "mcpServers" not in config_data:
            logger.error("Config file should contain 'mcpServers' key with server definitions")
            return servers

        mcp_servers_config = config_data["mcpServers"]
        if not isinstance(mcp_servers_config, dict):
            logger.error("mcpServers should be an object/dictionary")
            return servers

        for name, server_config in mcp_servers_config.items():
            if isinstance(server_config, dict):
                # Create a copy to avoid modifying the original
                config_copy = server_config.copy()
                # Add name to config
                config_copy["name"] = name
                try:
                    servers.append(MCPServer.model_validate(config_copy))
                except Exception as e:
                    logger.error(f"Failed to validate MCP server '{name}': {e}")
                    continue

        logger.info(f"Loaded {len(servers)} MCP servers from config file: {config_path}")

    except Exception as e:
        logger.error(f"Failed to parse MCP servers config file {config_path}: {e}")

    return servers


async def _sync_file_based_mcp_servers(storage: StorageDependency) -> None:
    """Sync file-based MCP servers with the storage.

    This function reads MCP servers from the config file and ensures they are
    present in the database with source=FILE. If there are name conflicts,
    it updates the existing server and changes its source to FILE. It also
    removes any FILE source servers that are no longer in the config file.

    Args:
        storage: Storage instance for database operations
    """
    try:
        file_servers = _read_mcp_servers_config_file()
        file_server_names = {server.name for server in file_servers}

        # Get all existing FILE source servers
        existing_file_servers = await storage.list_mcp_servers_by_source(MCPServerSource.FILE)

        # Remove FILE source servers that are no longer in the config file
        servers_to_remove = [
            (server_name, server_id)
            for server_name, server_id in existing_file_servers.items()
            if server_name not in file_server_names
        ]

        if servers_to_remove:
            server_ids_to_remove = [server_id for _, server_id in servers_to_remove]
            server_names_to_remove = [server_name for server_name, _ in servers_to_remove]

            try:
                logger.info(
                    f"Removing {len(servers_to_remove)} MCP servers as they're no longer in config "
                    f"file: {', '.join(server_names_to_remove)}"
                )
                await storage.delete_mcp_server(server_ids_to_remove)
            except Exception as e:
                logger.error(f"Failed to remove MCP servers {', '.join(server_names_to_remove)}: {e}")

        # Add/update servers from the config file
        for server in file_servers:
            try:
                mcp_server = await storage.get_mcp_server_by_name(server.name, MCPServerSource.FILE)

                if mcp_server:
                    # Server exists - update it and change source to FILE
                    mcp_server_id, _, _ = mcp_server
                    logger.info(f"Syncing existing MCP server '{server.name}'")
                    await storage.update_mcp_server(mcp_server_id, server, MCPServerSource.FILE)
                else:
                    # Server doesn't exist - create it with source FILE
                    logger.info(f"Creating new MCP server '{server.name}' from file")
                    await storage.create_mcp_server(server, MCPServerSource.FILE)

            except Exception as e:
                logger.error(f"Failed to sync MCP server '{server.name}' from file: {e}")
                # Continue with other servers
    except Exception as e:
        logger.error(f"Failed to sync file-based MCP servers: {e}")
        # No need to raise the exception, we'll just log it.


@router.post("/", response_model=MCPServerResponse)
async def create_mcp_server(
    payload: MCPServer,
    storage: StorageDependency,
    _: MCPQuotaCheck,
) -> MCPServerResponse:
    """Create an MCP server."""
    try:
        mcp_server_id = await storage.create_mcp_server(payload, source=MCPServerSource.API)
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"MCP server with name '{payload.name}' and source 'API' already exists",
        ) from e

    return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, payload)


@router.post("/mcp-servers-hosted", response_model=MCPServerResponse)
async def create_hosted_mcp_server(
    file: UploadFile,
    name: Annotated[str, Form()],
    storage: StorageDependency,
    _: MCPQuotaCheck,
    headers: Annotated[str | None, Form()] = None,
    mcp_server_metadata: Annotated[str | None, Form()] = None,
) -> MCPServerResponse:
    """Create a hosted MCP server by uploading a package file.

    This endpoint accepts multipart/form-data for deploying sema4ai_action_server
    type MCP servers that require a package file.

    Args:
        file: The .zip package file (max 50MB)
        name: Name of the MCP server
        headers: Optional JSON string of headers for the MCP server
        mcp_server_metadata: Optional JSON string of agent package inspection metadata
        storage: Storage dependency
        _: Quota check dependency

    Returns:
        MCPServerResponse with the created server details
    """
    parsed_headers = parse_mcp_headers_from_form(headers)

    # Parse mcp_server_metadata if provided
    parsed_metadata: dict | None = None
    if mcp_server_metadata:
        try:
            parsed_metadata = json.loads(mcp_server_metadata)
            if not isinstance(parsed_metadata, dict):
                raise PlatformHTTPError(
                    ErrorCode.BAD_REQUEST,
                    message="mcp_server_metadata must be a JSON object",
                )
        except json.JSONDecodeError as e:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                message=f"Invalid JSON in mcp_server_metadata field: {e}",
            ) from e

    deployment_id = str(uuid4())
    deployment_url = await deploy_mcp_server(file, deployment_id)

    mcp_server = MCPServer(
        name=name,
        type="sema4ai_action_server",
        url=deployment_url,
        headers=deserialize_mcp_variables(parsed_headers),
        mcp_server_metadata=parsed_metadata,
    )

    try:
        mcp_server_id = await storage.create_mcp_server(
            mcp_server, source=MCPServerSource.API, mcp_runtime_deployment_id=deployment_id
        )
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"MCP server with name '{name}' and source 'API' already exists",
        ) from e

    return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, mcp_server, is_hosted=True)


@router.get("/", response_model=dict[str, MCPServerResponse])
async def list_mcp_servers(
    storage: StorageDependency,
) -> dict[str, MCPServerResponse]:
    """List all MCP servers."""
    # Sync file-based servers before listing
    try:
        await _sync_file_based_mcp_servers(storage)
    except Exception as e:
        logger.error(f"Failed to sync file-based MCP servers in list endpoint: {e}")

    try:
        servers_with_metadata = await storage.list_mcp_servers_with_metadata()
        return {
            server_id: MCPServerResponse.from_mcp_server(
                server_id, meta.source, meta.server, is_hosted=meta.deployment_id is not None
            )
            for server_id, meta in servers_with_metadata.items()
        }
    except Exception as e:
        # Log unexpected errors during listing
        logger.error(f"Unexpected error while listing MCP servers: {e}")
        raise


@router.get("/{mcp_server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    mcp_server_id: str,
    storage: StorageDependency,
) -> MCPServerResponse:
    """Get a specific MCP server by ID."""
    try:
        # Sync file-based servers before getting
        try:
            await _sync_file_based_mcp_servers(storage)
        except Exception as e:
            logger.error(f"Failed to sync file-based MCP servers in get endpoint: {e}")

        meta = await storage.get_mcp_server_with_metadata(mcp_server_id)
        return MCPServerResponse.from_mcp_server(
            mcp_server_id, meta.source, meta.server, is_hosted=meta.deployment_id is not None
        )
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
    except ConfigDecryptionError as e:
        logger.error(f"Failed to decrypt MCP server configuration for {mcp_server_id}: {e}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Configuration data for MCP server {mcp_server_id} is corrupted and cannot be decrypted",
        ) from e


@router.put("/{mcp_server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    mcp_server_id: str,
    payload: MCPServer,
    storage: StorageDependency,
) -> MCPServerResponse:
    """Update an existing MCP server by ID"""
    try:
        await storage.update_mcp_server(mcp_server_id, payload, MCPServerSource.API)
        return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, payload)
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"MCP server with name '{payload.name}' and source 'API' already exists",
        ) from e


@router.delete("/{mcp_server_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_mcp_server(
    mcp_server_id: str,
    storage: StorageDependency,
) -> None:
    """Delete an MCP server."""
    # Delete from database and get deployment_id if any
    try:
        deleted_servers = await storage.delete_mcp_server([mcp_server_id])
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e

    # Best-effort cleanup of runtime deployment
    for server_id, deployment_id in deleted_servers:
        if deployment_id:
            success = await delete_deployment(deployment_id)
            if not success:
                logger.warning(
                    "Failed to delete MCP runtime deployment (database record already deleted)",
                    mcp_server_id=server_id,
                    deployment_id=deployment_id,
                )
