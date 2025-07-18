from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.storage import (
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=MCPServer)
async def upsert_mcp_server(
    payload: MCPServer,
    storage: StorageDependency,
) -> MCPServer:
    """Create or update an MCP server."""
    try:
        await storage.create_mcp_server(payload, source=MCPServerSource.API)
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server with name '{payload.name}' already exists",
        ) from e

    return payload


@router.get("/", response_model=dict[str, MCPServer])
async def list_mcp_servers(
    storage: StorageDependency,
) -> dict[str, MCPServer]:
    """List all MCP servers."""
    return await storage.list_mcp_servers()


@router.get("/{mcp_server_id}", response_model=MCPServer)
async def get_mcp_server(
    mcp_server_id: str,
    storage: StorageDependency,
) -> MCPServer:
    """Get a specific MCP server by ID."""
    try:
        return await storage.get_mcp_server(mcp_server_id)
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e


@router.put("/{mcp_server_id}", response_model=MCPServer)
async def update_mcp_server(
    mcp_server_id: str,
    payload: MCPServer,
    storage: StorageDependency,
) -> MCPServer:
    """Update an existing MCP server by ID"""
    try:
        await storage.update_mcp_server(mcp_server_id, payload, MCPServerSource.API)
        return payload
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
    except MCPServerWithNameAlreadyExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server with name '{payload.name}' already exists",
        ) from e


@router.delete("/{mcp_server_id}", status_code=204)
async def delete_mcp_server(
    mcp_server_id: str,
    storage: StorageDependency,
) -> None:
    """Delete an MCP server."""
    try:
        await storage.delete_mcp_server(mcp_server_id)
    except MCPServerNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server {mcp_server_id} not found",
        ) from e
