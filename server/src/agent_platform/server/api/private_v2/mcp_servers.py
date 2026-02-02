import json
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.payloads import MCPServerResponse
from agent_platform.core.payloads.mcp_server_payloads import MCPServerCreate, MCPServerUpdate
from agent_platform.core.payloads.mcp_server_response import MCPServerWithOAuthConfigResponse
from agent_platform.server.api.dependencies import MCPQuotaCheck, StorageDependency
from agent_platform.server.env_vars import SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE
from agent_platform.server.storage import (
    ConfigDecryptionError,
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
)

router = APIRouter()
logger = get_logger(__name__)


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
                    # Convert MCPServer to MCPServerUpdate for full update
                    update_payload = MCPServerUpdate(
                        name=server.name,
                        transport=server.transport,
                        url=server.url,
                        headers=server.headers,
                        command=server.command,
                        args=server.args,
                        env=server.env,
                        cwd=server.cwd,
                        force_serial_tool_calls=server.force_serial_tool_calls,
                        type=server.type,
                        mcp_server_metadata=server.mcp_server_metadata,
                        oauth_config=None,  # File-based servers don't have OAuth config
                    )
                    await storage.update_mcp_server(mcp_server_id, update_payload, MCPServerSource.FILE)
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
    payload: MCPServerCreate,
    storage: StorageDependency,
    _: MCPQuotaCheck,
) -> MCPServerResponse:
    """Create an MCP server."""
    from agent_platform.core.mcp.mcp_server import MCPServerWithOAuthConfig

    # Extract the name for response
    mcp_server_name = payload.name

    # Create MCPServerWithOAuthConfig from MCPServerCreate
    mcp_server: MCPServerWithOAuthConfig = payload.to_mcp_server()

    try:
        mcp_server_id = await storage.create_mcp_server(mcp_server, source=MCPServerSource.API)
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"MCP server with name '{mcp_server_name}' and source 'API' already exists",
        ) from e

    return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, mcp_server)


@router.get("/", response_model=dict[str, MCPServerWithOAuthConfigResponse])  # GET /api/v2/mcp-servers
async def list_mcp_servers(
    storage: StorageDependency,
) -> dict[str, MCPServerWithOAuthConfigResponse]:
    """List all MCP servers."""
    # Sync file-based servers before listing
    try:
        await _sync_file_based_mcp_servers(storage)
    except Exception as e:
        logger.error(f"Failed to sync file-based MCP servers in list endpoint: {e}")

    try:
        servers_with_metadata = await storage.list_mcp_servers_with_metadata()
        return {
            server_id: MCPServerWithOAuthConfigResponse.from_mcp_server_with_oauth_config(
                server_id, meta.source, meta.server
            )
            for server_id, meta in servers_with_metadata.items()
        }
    except Exception as e:
        # Log unexpected errors during listing
        logger.error(f"Unexpected error while listing MCP servers: {e}")
        raise


@router.get("/{mcp_server_id}", response_model=MCPServerWithOAuthConfigResponse)
async def get_mcp_server(  # GET /api/v2/mcp-servers/{mcp_server_id}
    mcp_server_id: str,
    storage: StorageDependency,
) -> MCPServerWithOAuthConfigResponse:
    """Get a specific MCP server by ID."""
    try:
        # Sync file-based servers before getting
        try:
            await _sync_file_based_mcp_servers(storage)
        except Exception as e:
            logger.error(f"Failed to sync file-based MCP servers in get endpoint: {e}")

        meta = await storage.get_mcp_server_with_metadata(mcp_server_id)
        return MCPServerWithOAuthConfigResponse.from_mcp_server_with_oauth_config(
            mcp_server_id, meta.source, meta.server
        )
    except MCPServerNotFoundError as e:
        raise PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            message=f"MCP server {mcp_server_id} not found",
        ) from e
    except ConfigDecryptionError as e:
        logger.error(f"Failed to decrypt MCP server configuration for {mcp_server_id}: {e}")
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED,
            message=f"Failed to decrypt MCP server configuration for {mcp_server_id}: {e}",
        ) from e


@router.put("/{mcp_server_id}", response_model=MCPServerResponse)
async def update_mcp_server(  # PUT /api/v2/mcp-servers/{mcp_server_id}
    mcp_server_id: str,
    payload: MCPServerUpdate,
    storage: StorageDependency,
) -> MCPServerResponse:
    """Update an existing MCP server by ID"""
    try:
        await storage.update_mcp_server(mcp_server_id, payload, MCPServerSource.API)
        # Get the updated server to return in response
        meta = await storage.get_mcp_server_with_metadata(mcp_server_id)
        return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, meta.server)
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
    try:
        await storage.delete_mcp_server([mcp_server_id])
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
