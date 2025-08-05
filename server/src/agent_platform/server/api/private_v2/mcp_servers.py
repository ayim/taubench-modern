import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.core.payloads import MCPServerResponse
from agent_platform.server.api.dependencies import MCPQuotaCheck, StorageDependency
from agent_platform.server.env_vars import SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE
from agent_platform.server.storage import (
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
                logger.error(
                    f"Failed to remove MCP servers {', '.join(server_names_to_remove)}: {e}"
                )

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
async def upsert_mcp_server(
    payload: MCPServer,
    storage: StorageDependency,
    _: MCPQuotaCheck,
) -> MCPServerResponse:
    """Create or update an MCP server."""
    try:
        mcp_server_id = await storage.create_mcp_server(payload, source=MCPServerSource.API)
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server with name '{payload.name}' and source 'API' already exists",
        ) from e

    return MCPServerResponse.from_mcp_server(mcp_server_id, MCPServerSource.API, payload)


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

    servers_with_metadata = await storage.list_mcp_servers_with_metadata()
    return {
        server_id: MCPServerResponse.from_mcp_server(server_id, source, mcp_server)
        for server_id, (mcp_server, source) in servers_with_metadata.items()
    }


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

        mcp_server, source = await storage.get_mcp_server_with_metadata(mcp_server_id)
        return MCPServerResponse.from_mcp_server(mcp_server_id, source, mcp_server)
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
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
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server with name '{payload.name}' and source 'API' already exists",
        ) from e


@router.delete("/{mcp_server_id}", status_code=204)
async def delete_mcp_server(
    mcp_server_id: str,
    storage: StorageDependency,
) -> None:
    """Delete an MCP server."""
    try:
        await storage.delete_mcp_server([mcp_server_id])
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
