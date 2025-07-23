import pytest

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.errors import (
    InvalidUUIDError,
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
)
from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_mcp_server_crud_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
) -> None:
    """Test Create, Read, Update, and Delete operations for MCP servers."""

    # Create
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)

    # List all servers to get the server ID
    servers_dict = await storage.list_mcp_servers()
    assert len(servers_dict) == 1
    server_id = next(iter(servers_dict.keys()))
    retrieved_server = servers_dict[server_id]

    # Verify the retrieved server matches the original
    assert retrieved_server.name == sample_mcp_server_http.name
    assert retrieved_server.transport == sample_mcp_server_http.transport
    assert retrieved_server.url == sample_mcp_server_http.url
    assert retrieved_server.headers == sample_mcp_server_http.headers

    # Read by ID
    server_by_id = await storage.get_mcp_server(server_id)
    assert server_by_id.name == sample_mcp_server_http.name
    assert server_by_id.transport == sample_mcp_server_http.transport

    # Update
    updated_server = MCPServer(
        name="updated-test-server",
        transport="streamable-http",
        url="https://updated.example.com/mcp",
        headers={"Authorization": "Bearer updated-token"},
    )
    await storage.update_mcp_server(server_id, updated_server, MCPServerSource.API)

    # Verify update
    updated_retrieved = await storage.get_mcp_server(server_id)
    assert updated_retrieved.name == "updated-test-server"
    assert updated_retrieved.url == "https://updated.example.com/mcp"
    assert updated_retrieved.headers == {"Authorization": "Bearer updated-token"}

    # Delete
    await storage.delete_mcp_server([server_id])

    # Verify deletion
    with pytest.raises(MCPServerNotFoundError):
        await storage.get_mcp_server(server_id)

    # Verify list is empty
    servers_after_delete = await storage.list_mcp_servers()
    assert len(servers_after_delete) == 0


@pytest.mark.asyncio
async def test_mcp_server_list_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
    sample_mcp_server_sse: MCPServer,
) -> None:
    """Test listing multiple MCP servers."""

    # Create multiple servers
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_sse, MCPServerSource.API)

    # List all servers
    servers_dict = await storage.list_mcp_servers()
    assert len(servers_dict) == 3

    # Verify all servers are present
    server_names = {server.name for server in servers_dict.values()}
    expected_names = {
        sample_mcp_server_http.name,
        sample_mcp_server_stdio.name,
        sample_mcp_server_sse.name,
    }
    assert server_names == expected_names

    # Verify the return type is dict[str, MCPServer]
    assert isinstance(servers_dict, dict)
    for server_id, server in servers_dict.items():
        assert isinstance(server_id, str)
        assert isinstance(server, MCPServer)


@pytest.mark.asyncio
async def test_mcp_server_duplicate_name_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
) -> None:
    """Test that creating MCP servers with duplicate names raises an error."""

    # Create the first server
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)

    # Try to create another server with the same name
    duplicate_server = MCPServer(
        name=sample_mcp_server_http.name,  # Same name
        transport="sse",
        url="https://different.example.com/sse",
    )

    with pytest.raises(MCPServerWithNameAlreadyExistsError):
        await storage.create_mcp_server(duplicate_server, MCPServerSource.API)


@pytest.mark.asyncio
async def test_mcp_server_not_found_error(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that getting non-existent MCP server raises an error."""

    non_existent_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(MCPServerNotFoundError):
        await storage.get_mcp_server(non_existent_id)


@pytest.mark.asyncio
async def test_mcp_server_invalid_uuid_error(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that invalid UUIDs raise an error."""

    invalid_uuid = "not-a-uuid"

    with pytest.raises(InvalidUUIDError):
        await storage.get_mcp_server(invalid_uuid)


@pytest.mark.asyncio
async def test_mcp_server_empty_list(
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test that listing MCP servers returns empty dict when no servers exist."""

    servers = await storage.list_mcp_servers()
    assert isinstance(servers, dict)
    assert len(servers) == 0


@pytest.mark.asyncio
async def test_mcp_server_different_transports(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
    sample_mcp_server_sse: MCPServer,
) -> None:
    """Test creating and retrieving MCP servers with different transport types."""

    # Create servers with different transports
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_sse, MCPServerSource.API)

    servers = await storage.list_mcp_servers()

    # Find each server by name and verify transport-specific fields
    for server in servers.values():
        if server.name == "test-http-server":
            assert server.transport == "streamable-http"
            assert server.url == "https://example.com/mcp"
            assert server.headers == {"Authorization": "Bearer test-token"}
            assert server.command is None
            assert server.args is None
        elif server.name == "test-stdio-server":
            assert server.transport == "stdio"
            assert server.command == "python"
            assert server.args == ["-m", "mcp_test_server"]
            assert server.env == {"TEST_ENV": "test_value"}
            assert server.cwd == "/tmp"
            assert server.url is None
        elif server.name == "test-sse-server":
            assert server.transport == "sse"
            assert server.url == "https://example.com/sse"
            assert server.command is None


@pytest.mark.asyncio
async def test_get_mcp_server_by_name(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
) -> None:
    """Test getting MCP server by name."""
    # Create servers
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.FILE)

    # Test getting existing server by name
    result = await storage.get_mcp_server_by_name(sample_mcp_server_http.name, MCPServerSource.API)
    assert result is not None
    server_id, server, source = result
    assert server.name == sample_mcp_server_http.name
    assert server.transport == sample_mcp_server_http.transport
    assert source == MCPServerSource.API

    # Test getting FILE source server
    result_file = await storage.get_mcp_server_by_name(
        sample_mcp_server_stdio.name, MCPServerSource.FILE
    )
    assert result_file is not None
    server_id_file, server_file, source_file = result_file
    assert server_file.name == sample_mcp_server_stdio.name
    assert source_file == MCPServerSource.FILE

    # Test getting non-existent server
    result_none = await storage.get_mcp_server_by_name("non-existent-server", MCPServerSource.API)
    assert result_none is None


@pytest.mark.asyncio
async def test_list_mcp_servers_by_source(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
    sample_mcp_server_sse: MCPServer,
) -> None:
    """Test listing MCP servers by source."""
    # Create servers with different sources
    await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.FILE)
    await storage.create_mcp_server(sample_mcp_server_sse, MCPServerSource.FILE)

    # Test listing API source servers
    api_servers = await storage.list_mcp_servers_by_source(MCPServerSource.API)
    assert len(api_servers) == 1
    assert sample_mcp_server_http.name in api_servers

    # Test listing FILE source servers
    file_servers = await storage.list_mcp_servers_by_source(MCPServerSource.FILE)
    assert len(file_servers) == 2
    assert sample_mcp_server_stdio.name in file_servers
    assert sample_mcp_server_sse.name in file_servers

    # Test with no servers of a given source
    # Since we removed user_id, we just verify the method works
    empty_result = await storage.list_mcp_servers_by_source(MCPServerSource.API)
    assert isinstance(empty_result, dict)


@pytest.mark.asyncio
async def test_get_mcp_server_by_name_with_invalid_name(
    storage: SQLiteStorage,
) -> None:
    """Test get_mcp_server_by_name with invalid server name."""
    # Since user_id is removed, test with non-existent server name
    result = await storage.get_mcp_server_by_name("non-existent-server", MCPServerSource.API)
    assert result is None


@pytest.mark.asyncio
async def test_list_mcp_servers_by_source_empty(
    storage: SQLiteStorage,
) -> None:
    """Test list_mcp_servers_by_source when no servers exist for source."""
    # Since user_id is removed, test empty result for a source
    result = await storage.list_mcp_servers_by_source(MCPServerSource.API)
    assert isinstance(result, dict)
    assert len(result) == 0


async def test_list_mcp_servers_with_metadata(
    storage: SQLiteStorage,
    sample_mcp_server_http: MCPServer,
    sample_mcp_server_stdio: MCPServer,
):
    """Test listing MCP servers with metadata (server data + source)."""
    # Create servers with different sources
    server1_id = await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)
    server2_id = await storage.create_mcp_server(sample_mcp_server_stdio, MCPServerSource.FILE)

    # List servers with metadata
    servers_with_metadata = await storage.list_mcp_servers_with_metadata()

    # Verify both servers are returned with correct metadata
    assert len(servers_with_metadata) == 2
    assert server1_id in servers_with_metadata
    assert server2_id in servers_with_metadata

    # Check server 1 (API source)
    server1_data, server1_source = servers_with_metadata[server1_id]
    assert server1_data.name == sample_mcp_server_http.name
    assert server1_data.transport == sample_mcp_server_http.transport
    assert server1_source == MCPServerSource.API

    # Check server 2 (FILE source)
    server2_data, server2_source = servers_with_metadata[server2_id]
    assert server2_data.name == sample_mcp_server_stdio.name
    assert server2_data.transport == sample_mcp_server_stdio.transport
    assert server2_source == MCPServerSource.FILE


async def test_get_mcp_server_with_metadata(
    storage: SQLiteStorage,
    sample_mcp_server_http: MCPServer,
):
    """Test getting an MCP server with metadata (server data + source)."""
    # Create server
    server_id = await storage.create_mcp_server(sample_mcp_server_http, MCPServerSource.API)

    # Get server with metadata
    server_data, source = await storage.get_mcp_server_with_metadata(server_id)

    # Verify server data
    assert server_data.name == sample_mcp_server_http.name
    assert server_data.transport == sample_mcp_server_http.transport
    assert server_data.url == sample_mcp_server_http.url
    assert server_data.headers == sample_mcp_server_http.headers

    # Verify source
    assert source == MCPServerSource.API


async def test_get_mcp_server_with_metadata_not_found(
    storage: SQLiteStorage,
):
    """Test get_mcp_server_with_metadata with non-existent server."""
    from uuid import uuid4

    non_existent_id = str(uuid4())

    with pytest.raises(MCPServerNotFoundError):
        await storage.get_mcp_server_with_metadata(non_existent_id)


async def test_list_mcp_servers_with_metadata_empty(
    storage: SQLiteStorage,
):
    """Test list_mcp_servers_with_metadata when no servers exist."""
    result = await storage.list_mcp_servers_with_metadata()
    assert result == {}
