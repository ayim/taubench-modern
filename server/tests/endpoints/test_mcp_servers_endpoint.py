import pytest
from fastapi.testclient import TestClient


def skip_postgres_enum_issue(request):
    """Skip test for PostgreSQL in full test suite due to enum caching issue."""
    if hasattr(request, "node") and "postgres" in str(
        request.node.callspec.params.get("storage", "")
    ):
        pytest.skip("Skipping PostgreSQL test due to enum caching issue in test suite")


@pytest.fixture
def sample_mcp_server_payload():
    """Sample MCP server payload for API requests."""
    return {
        "name": "test-api-server",
        "transport": "streamable-http",
        "url": "https://api.example.com/mcp",
        "headers": {"Authorization": "Bearer test-token"},
    }


@pytest.fixture
def sample_mcp_server_stdio_payload():
    """Sample MCP server stdio payload for API requests."""
    return {
        "name": "test-stdio-api-server",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "test_mcp_server"],
        "env": {"TEST_ENV": "api_test"},
        "cwd": "/tmp",
    }


def test_create_mcp_server(client: TestClient, sample_mcp_server_payload: dict):
    """Test creating an MCP server via API."""
    response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_mcp_server_payload["name"]
    assert data["transport"] == sample_mcp_server_payload["transport"]
    assert data["url"] == sample_mcp_server_payload["url"]
    assert data["headers"] == sample_mcp_server_payload["headers"]


def test_create_mcp_server_duplicate_name(client: TestClient, sample_mcp_server_payload: dict):
    """Test that creating MCP servers with duplicate names returns 409."""
    # Create first server
    response1 = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert response1.status_code == 200

    # Try to create second server with same name
    response2 = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert response2.status_code == 409
    # Check the error message in the nested error object
    response_json = response2.json()
    error_message = (
        response_json.get("detail")
        or response_json.get("message", "")
        or response_json.get("error", {}).get("message", "")
    )
    assert "already exists" in error_message


def test_list_mcp_servers_empty(client: TestClient):
    """Test listing MCP servers when none exist."""
    response = client.get("/api/v2/private/mcp-servers/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) == 0


def test_list_mcp_servers_multiple(
    client: TestClient, sample_mcp_server_payload: dict, sample_mcp_server_stdio_payload: dict
):
    """Test listing multiple MCP servers."""
    # Create two servers
    response1 = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert response1.status_code == 200

    response2 = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_stdio_payload)
    assert response2.status_code == 200

    # List servers
    response = client.get("/api/v2/private/mcp-servers/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert len(data) == 2

    # Verify the servers are in the response
    server_names = {server["name"] for server in data.values()}
    expected_names = {sample_mcp_server_payload["name"], sample_mcp_server_stdio_payload["name"]}
    assert server_names == expected_names


def test_get_mcp_server_by_id(client: TestClient, sample_mcp_server_payload: dict):
    """Test getting a specific MCP server by ID."""
    # Create a server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # Get server ID from list
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    server_id = next(iter(servers.keys()))

    # Get specific server
    response = client.get(f"/api/v2/private/mcp-servers/{server_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == sample_mcp_server_payload["name"]
    assert data["transport"] == sample_mcp_server_payload["transport"]
    assert data["url"] == sample_mcp_server_payload["url"]


def test_get_mcp_server_not_found(client: TestClient):
    """Test getting a non-existent MCP server returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v2/private/mcp-servers/{non_existent_id}")

    assert response.status_code == 404


def test_update_mcp_server(client: TestClient, sample_mcp_server_payload: dict):
    """Test updating an MCP server."""
    # Create a server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # Get server ID
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    server_id = next(iter(servers.keys()))

    # Update the server
    updated_payload = {
        "name": "updated-test-server",
        "transport": "streamable-http",
        "url": "https://updated.example.com/mcp",
        "headers": {"Authorization": "Bearer updated-token"},
    }

    response = client.put(f"/api/v2/private/mcp-servers/{server_id}", json=updated_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "updated-test-server"
    assert data["url"] == "https://updated.example.com/mcp"
    assert data["headers"] == {"Authorization": "Bearer updated-token"}


def test_update_mcp_server_not_found(client: TestClient, sample_mcp_server_payload: dict):
    """Test updating a non-existent MCP server returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.put(
        f"/api/v2/private/mcp-servers/{non_existent_id}", json=sample_mcp_server_payload
    )

    assert response.status_code == 404


def test_delete_mcp_server(client: TestClient, sample_mcp_server_payload: dict):
    """Test deleting an MCP server."""
    # Create a server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # Get server ID
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    server_id = next(iter(servers.keys()))

    # Delete the server
    delete_response = client.delete(f"/api/v2/private/mcp-servers/{server_id}")
    assert delete_response.status_code == 204

    # Verify deletion
    get_response = client.get(f"/api/v2/private/mcp-servers/{server_id}")
    assert get_response.status_code == 404

    # Verify list is empty
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    assert len(servers) == 0


def test_delete_mcp_server_not_found(client: TestClient):
    """Test deleting a non-existent MCP server returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/v2/private/mcp-servers/{non_existent_id}")

    assert response.status_code == 404


def test_create_mcp_server_stdio_transport(
    client: TestClient, sample_mcp_server_stdio_payload: dict, request
):
    """Test creating an MCP server with stdio transport."""
    skip_postgres_enum_issue(request)

    response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_stdio_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == sample_mcp_server_stdio_payload["name"]
    assert data["transport"] == "stdio"
    assert data["command"] == "python"
    assert data["args"] == ["-m", "test_mcp_server"]
    assert data["env"] == {"TEST_ENV": "api_test"}
    assert data["cwd"] == "/tmp"
    assert data["url"] is None


def test_create_mcp_server_sse_transport(client: TestClient, request):
    """Test creating an MCP server with SSE transport."""
    skip_postgres_enum_issue(request)

    sse_payload = {"name": "test-sse-server", "transport": "sse", "url": "https://example.com/sse"}

    response = client.post("/api/v2/private/mcp-servers/", json=sse_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-sse-server"
    assert data["transport"] == "sse"
    assert data["url"] == "https://example.com/sse"
    assert data["command"] is None


def test_create_mcp_server_auto_transport(client: TestClient, request):
    """Test creating an MCP server with auto transport (should default to streamable-http)."""
    skip_postgres_enum_issue(request)

    auto_payload = {
        "name": "test-auto-server",
        "transport": "auto",
        "url": "https://example.com/mcp",
    }

    response = client.post("/api/v2/private/mcp-servers/", json=auto_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-auto-server"
    assert data["transport"] == "streamable-http"  # Should be resolved to streamable-http
    assert data["url"] == "https://example.com/mcp"


def test_create_mcp_server_validation_error(client: TestClient):
    """Test creating an MCP server with invalid data returns 422."""
    invalid_payload = {
        "name": "test-server",
        # Missing transport and both url/command - should be invalid
    }

    response = client.post("/api/v2/private/mcp-servers/", json=invalid_payload)

    assert response.status_code == 422  # Validation error


def test_list_mcp_servers_with_nonexistent_ids(client: TestClient):
    """Test filtering by non-existent IDs returns empty dict."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v2/private/mcp-servers/?ids={non_existent_id}")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) == 0


def test_mcp_server_response_format(client: TestClient, sample_mcp_server_payload: dict):
    """Test that the response format matches expectations for dict[str, MCPServer]."""
    # Create a server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # List servers
    list_response = client.get("/api/v2/private/mcp-servers/")
    assert list_response.status_code == 200

    data = list_response.json()

    # Verify it's a dictionary
    assert isinstance(data, dict)

    # Verify each key is a string (UUID) and each value is an MCPServer object
    for server_id, server_data in data.items():
        assert isinstance(server_id, str)
        assert isinstance(server_data, dict)

        # Verify required MCPServer fields are present
        assert "name" in server_data
        assert "transport" in server_data
        assert server_data["name"] == sample_mcp_server_payload["name"]
        assert server_data["transport"] == sample_mcp_server_payload["transport"]
