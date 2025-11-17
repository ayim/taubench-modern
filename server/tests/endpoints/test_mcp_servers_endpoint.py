from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent_platform.server.storage.errors import ConfigDecryptionError


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
    """Test the format of MCP server responses."""
    # Create server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200
    created_data = create_response.json()

    # Verify create response has MCPServerResponse format
    expected_fields = [
        "mcp_server_id",
        "source",
        "name",
        "transport",
        "url",
        "headers",
        "command",
        "args",
        "env",
        "cwd",
        "force_serial_tool_calls",
    ]
    for field in expected_fields:
        assert field in created_data

    # Verify created server has correct source and values
    assert created_data["source"] == "API"
    assert created_data["name"] == sample_mcp_server_payload["name"]
    assert created_data["transport"] == sample_mcp_server_payload["transport"]
    assert created_data["url"] == sample_mcp_server_payload["url"]
    assert created_data["headers"] == sample_mcp_server_payload["headers"]

    # Get the created server ID from the list
    list_response = client.get("/api/v2/private/mcp-servers/")
    assert list_response.status_code == 200
    servers = list_response.json()
    assert len(servers) == 1
    server_id = next(iter(servers.keys()))

    # Verify list response format
    list_server_data = servers[server_id]
    for field in expected_fields:
        assert field in list_server_data
    assert list_server_data["source"] == "API"

    # Get individual server
    get_response = client.get(f"/api/v2/private/mcp-servers/{server_id}")
    assert get_response.status_code == 200
    server_data = get_response.json()

    # Verify individual get response format
    for field in expected_fields:
        assert field in server_data

    # Verify specific values
    assert server_data["mcp_server_id"] == server_id
    assert server_data["source"] == "API"
    assert server_data["name"] == sample_mcp_server_payload["name"]
    assert server_data["transport"] == sample_mcp_server_payload["transport"]


@patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers")
def test_list_mcp_servers_calls_sync(mock_sync, client: TestClient):
    """Test that list_mcp_servers calls the sync function."""
    # Make the request
    response = client.get("/api/v2/private/mcp-servers/")
    assert response.status_code == 200

    # Verify sync was called
    mock_sync.assert_called_once()


@patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers")
def test_get_mcp_server_calls_sync(mock_sync, client: TestClient, sample_mcp_server_payload: dict):
    """Test that get_mcp_server calls the sync function."""
    # Create a server first
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # Get server list to find the ID
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    server_id = next(iter(servers.keys()))

    # Reset the mock to only count the get_mcp_server call
    mock_sync.reset_mock()

    # Make the get request
    response = client.get(f"/api/v2/private/mcp-servers/{server_id}")
    assert response.status_code == 200

    # Verify sync was called
    mock_sync.assert_called_once()


@patch("agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file")
def test_list_includes_file_based_servers(
    mock_read_config, client: TestClient, sample_mcp_server_payload: dict
):
    """Test that file-based servers are included in the list after sync."""
    # Mock file-based server from config
    from agent_platform.core.mcp.mcp_server import MCPServer

    file_server = MCPServer(
        name="file-based-server",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
    )
    mock_read_config.return_value = [file_server]

    # Create an API server
    create_response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert create_response.status_code == 200

    # List servers (this will trigger sync)
    list_response = client.get("/api/v2/private/mcp-servers/")
    assert list_response.status_code == 200
    servers = list_response.json()

    # Should have both API and FILE servers
    assert len(servers) == 2
    server_names = [server["name"] for server in servers.values()]
    assert sample_mcp_server_payload["name"] in server_names
    assert "file-based-server" in server_names


@patch("agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file")
def test_sync_removes_obsolete_file_servers(mock_read_config, client: TestClient):
    """Test that obsolete file-based servers are removed during sync."""
    from agent_platform.core.mcp.mcp_server import MCPServer

    # First, create a file server by mocking a config with it
    file_server = MCPServer(name="temp-file-server", transport="stdio", command="test")
    mock_read_config.return_value = [file_server]

    # List servers to create the file server
    list_response = client.get("/api/v2/private/mcp-servers/")
    assert list_response.status_code == 200
    servers = list_response.json()
    assert len(servers) == 1
    assert "temp-file-server" in [s["name"] for s in servers.values()]

    # Now mock empty config (server removed from file)
    mock_read_config.return_value = []

    # List again - should remove the file server
    list_response = client.get("/api/v2/private/mcp-servers/")
    assert list_response.status_code == 200
    servers = list_response.json()
    assert len(servers) == 0


@patch("agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file")
def test_sync_updates_existing_file_server(mock_read_config, client: TestClient):
    """Test that existing file-based servers are updated during sync."""
    from agent_platform.core.mcp.mcp_server import MCPServer

    # Create initial file server
    original_server = MCPServer(name="update-me-server", transport="stdio", command="old-command")
    mock_read_config.return_value = [original_server]

    # List servers to create the file server
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    assert len(servers) == 1
    original_command = next(iter(servers.values()))["command"]
    assert original_command == "old-command"

    # Update the server config
    updated_server = MCPServer(
        name="update-me-server",  # Same name
        transport="stdio",
        command="new-command",  # Different command
        args=["-new", "args"],
    )
    mock_read_config.return_value = [updated_server]

    # List again - should update the server
    list_response = client.get("/api/v2/private/mcp-servers/")
    servers = list_response.json()
    assert len(servers) == 1
    updated_command = next(iter(servers.values()))["command"]
    updated_args = next(iter(servers.values()))["args"]
    assert updated_command == "new-command"
    assert updated_args == ["-new", "args"]


def test_sync_error_handling(client: TestClient):
    """Test that sync errors don't break the API endpoints."""
    with patch(
        "agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"
    ) as mock_sync:
        # Make sync raise an exception
        mock_sync.side_effect = Exception("Sync failed")

        # List should still work (sync errors are caught and logged)
        response = client.get("/api/v2/private/mcp-servers/")
        # The API should still return 200 even if sync fails
        assert response.status_code == 200
        assert isinstance(response.json(), dict)


def test_create_mcp_server_quota_exceeded(fastapi_app, sample_mcp_server_payload: dict):
    """Test that MCP server creation is blocked when quota is exceeded."""
    from starlette.testclient import TestClient

    from agent_platform.core.errors.quotas import MCPServerQuotaExceededError
    from agent_platform.server.api.dependencies import check_mcp_server_quota

    # Mock the quota check dependency to raise the quota exceeded error
    async def mock_quota_check_exceeded():
        raise MCPServerQuotaExceededError(current_count=3, quota_limit=2)

    # Override the dependency in the FastAPI app
    fastapi_app.dependency_overrides[check_mcp_server_quota] = mock_quota_check_exceeded

    try:
        # Create a client with the modified app
        client = TestClient(fastapi_app)

        # Attempt to create an MCP server
        response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)

        # Should receive 429 Too Many Requests
        assert response.status_code == 429

    finally:
        # Clean up the dependency override
        fastapi_app.dependency_overrides.clear()


def test_create_mcp_server_quota_within_limit(fastapi_app, sample_mcp_server_payload: dict):
    """Test that MCP server creation succeeds when within quota limits."""
    from starlette.testclient import TestClient

    from agent_platform.server.api.dependencies import check_mcp_server_quota

    # Mock the quota check dependency to pass (do nothing)
    async def mock_quota_check_pass():
        # This dependency should pass without raising any exception
        pass

    # Override the dependency in the FastAPI app
    fastapi_app.dependency_overrides[check_mcp_server_quota] = mock_quota_check_pass

    try:
        # Create a client with the modified app
        client = TestClient(fastapi_app)

        # Attempt to create an MCP server
        response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)

        # Should succeed with 200 OK
        assert response.status_code == 200
        mcp_server_data = response.json()

        # Verify response structure
        assert "mcp_server_id" in mcp_server_data
        assert mcp_server_data["name"] == sample_mcp_server_payload["name"]
        assert mcp_server_data["transport"] == sample_mcp_server_payload["transport"]

    finally:
        # Clean up the dependency override
        fastapi_app.dependency_overrides.clear()


def test_create_mcp_server_has_quota_check():
    """Test that the create_mcp_server endpoint has the quota check dependency."""
    import inspect

    from agent_platform.server.api.private_v2.mcp_servers import create_mcp_server

    # Get the function signature
    sig = inspect.signature(create_mcp_server)

    # Check that MCPQuotaCheck is in the parameters
    param_names = list(sig.parameters.keys())

    # The quota check should be present as a parameter
    assert "_" in param_names  # The quota check parameter is named "_"

    # Verify the parameter annotation contains the quota check
    quota_param = sig.parameters["_"]
    assert "check_mcp_server_quota" in str(quota_param.annotation)


def test_get_mcp_server_decryption_error(
    client: TestClient, sample_mcp_server_payload: dict, storage
):
    """Test GET MCP server endpoint with decryption error."""
    # First create an MCP server
    response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert response.status_code == 200
    server_id = response.json()["mcp_server_id"]

    # Mock the storage method to raise ConfigDecryptionError
    with patch.object(storage, "get_mcp_server_with_metadata") as mock_get_metadata:
        mock_get_metadata.side_effect = ConfigDecryptionError(
            f"Failed to decrypt MCP server configuration for {server_id}"
        )

        # Mock the sync function to avoid side effects
        with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
            # Make the request
            response = client.get(f"/api/v2/private/mcp-servers/{server_id}")

        # Should return 500 with proper error message
        assert response.status_code == 500
        response_data = response.json()
        # Check if it's in the standard error format {"error": {"message": "..."}}
        if "error" in response_data:
            error_message = response_data["error"]["message"]
        else:
            error_message = response_data.get("detail", "")

        assert "corrupted and cannot be decrypted" in error_message
        assert server_id in error_message


def test_list_mcp_servers_with_partial_decryption_failure(
    client: TestClient, sample_mcp_server_payload: dict, storage
):
    """Test LIST MCP servers endpoint continues to work when some servers have decryption errors."""
    # First create an MCP server
    response = client.post("/api/v2/private/mcp-servers/", json=sample_mcp_server_payload)
    assert response.status_code == 200

    # Mock the storage method to return partial results (simulate some entries skipped due to
    # decryption errors)
    from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource

    # Simulate that only one server is returned (others were skipped due to decryption errors)
    mock_server = MCPServer.model_validate(
        {
            "name": "working-server",
            "transport": "streamable-http",
            "url": "https://working.example.com/mcp",
        }
    )

    with patch.object(storage, "list_mcp_servers_with_metadata") as mock_list_metadata:
        mock_list_metadata.return_value = {"working-server-id": (mock_server, MCPServerSource.API)}

        # Mock the sync function to avoid side effects
        with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
            # Make the request
            response = client.get("/api/v2/private/mcp-servers/")

        # Should succeed and return only the working server
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "working-server-id" in data
        assert data["working-server-id"]["name"] == "working-server"


def test_upload_mcp_server_success(client: TestClient):
    """Test uploading an MCP server package successfully."""
    import io
    from unittest.mock import AsyncMock, patch

    from agent_platform.server.api.private_v2.mcp_servers import MCPRuntimeDeploymentResponse

    # Create a minimal zip file content
    zip_content = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(zip_content, "w") as zf:
        zf.writestr("test.txt", "test content")
    zip_content.seek(0)

    # Prepare the multipart form data
    files = {"file": ("test-package.zip", zip_content, "application/zip")}
    data = {
        "name": "test-action-server",
        "headers": '{"X-API-Key": "test-key"}',
    }

    # Mock the MCP Runtime API call function
    mock_deployment_response = MCPRuntimeDeploymentResponse(
        url="https://deployed-mcp-server.example.com/endpoint",
        status="running",
        deployment_id="test-deployment-123",
    )

    with patch(
        "agent_platform.server.api.private_v2.mcp_servers.call_mcp_runtime_deployment_api",
        new_callable=AsyncMock,
        return_value=mock_deployment_response,
    ) as mock_api_call:
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

        # Verify the API call function was called
        assert mock_api_call.called
        call_args = mock_api_call.call_args
        # Check that URL contains /api/deployments/{uuid}
        assert "/api/deployments/" in call_args[0][0]
        # Check that file content was passed
        assert len(call_args[0][1]) > 0

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == "test-action-server"
    assert response_data["type"] == "sema4ai_action_server"
    assert response_data["url"] == "https://deployed-mcp-server.example.com/endpoint"
    assert response_data["headers"] == {"X-API-Key": "test-key"}
    assert response_data["source"] == "API"
    assert "mcp_server_id" in response_data


def test_upload_mcp_server_without_headers(client: TestClient):
    """Test uploading an MCP server package without optional headers."""
    import io
    import zipfile
    from unittest.mock import AsyncMock, patch

    from agent_platform.server.api.private_v2.mcp_servers import MCPRuntimeDeploymentResponse

    zip_content = io.BytesIO()
    with zipfile.ZipFile(zip_content, "w") as zf:
        zf.writestr("test.txt", "test content")
    zip_content.seek(0)

    files = {"file": ("test-package.zip", zip_content, "application/zip")}
    data = {"name": "test-action-server-no-headers"}

    # Mock the MCP Runtime API call function
    mock_deployment_response = MCPRuntimeDeploymentResponse(
        url="https://deployed-mcp-server.example.com/endpoint",
        status="running",
        deployment_id="test-deployment-456",
    )

    with patch(
        "agent_platform.server.api.private_v2.mcp_servers.call_mcp_runtime_deployment_api",
        new_callable=AsyncMock,
        return_value=mock_deployment_response,
    ):
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == "test-action-server-no-headers"
    assert response_data["headers"] is None


def test_upload_mcp_server_invalid_file_extension(client: TestClient):
    """Test that uploading a non-zip file is rejected."""
    import io
    from unittest.mock import patch

    file_content = io.BytesIO(b"not a zip file")
    files = {"file": ("test-package.txt", file_content, "text/plain")}
    data = {"name": "test-action-server"}

    with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response.status_code == 400
    response_data = response.json()
    error_message = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "zip" in error_message.lower()


def test_upload_mcp_server_file_too_large(client: TestClient):
    """Test that uploading a file exceeding 50MB is rejected."""
    import io
    import zipfile
    from unittest.mock import patch

    # Create a zip file larger than 50MB
    zip_content = io.BytesIO()
    with zipfile.ZipFile(zip_content, "w", zipfile.ZIP_STORED) as zf:
        # Add a file with 51MB of data
        large_data = b"x" * (51 * 1024 * 1024)
        zf.writestr("large_file.bin", large_data)
    zip_content.seek(0)

    files = {"file": ("large-package.zip", zip_content, "application/zip")}
    data = {"name": "test-action-server"}

    with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response.status_code == 413
    response_data = response.json()
    error_message = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "exceeds maximum allowed size" in error_message


def test_upload_mcp_server_invalid_headers_json(client: TestClient):
    """Test that invalid JSON in headers field is rejected."""
    import io
    import zipfile
    from unittest.mock import patch

    zip_content = io.BytesIO()
    with zipfile.ZipFile(zip_content, "w") as zf:
        zf.writestr("test.txt", "test content")
    zip_content.seek(0)

    files = {"file": ("test-package.zip", zip_content, "application/zip")}
    data = {
        "name": "test-action-server",
        "headers": "not valid json",
    }

    with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response.status_code == 400
    response_data = response.json()
    error_message = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "Invalid JSON" in error_message


def test_upload_mcp_server_headers_not_object(client: TestClient):
    """Test that headers must be a JSON object, not an array or string."""
    import io
    import zipfile
    from unittest.mock import patch

    zip_content = io.BytesIO()
    with zipfile.ZipFile(zip_content, "w") as zf:
        zf.writestr("test.txt", "test content")
    zip_content.seek(0)

    files = {"file": ("test-package.zip", zip_content, "application/zip")}
    data = {
        "name": "test-action-server",
        "headers": '["not", "an", "object"]',
    }

    with patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"):
        response = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response.status_code == 400
    response_data = response.json()
    error_message = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "must be a JSON object" in error_message


def test_upload_mcp_server_duplicate_name(client: TestClient):
    """Test that uploading with duplicate name returns 409."""
    import io
    import zipfile
    from unittest.mock import AsyncMock, patch

    from agent_platform.server.api.private_v2.mcp_servers import MCPRuntimeDeploymentResponse

    zip_content = io.BytesIO()
    with zipfile.ZipFile(zip_content, "w") as zf:
        zf.writestr("test.txt", "test content")
    zip_content.seek(0)

    files = {"file": ("test-package.zip", zip_content, "application/zip")}
    data = {"name": "duplicate-server"}

    # Mock the MCP Runtime API call function
    mock_deployment_response = MCPRuntimeDeploymentResponse(
        url="https://deployed-mcp-server.example.com/endpoint",
        status="running",
        deployment_id="test-deployment-789",
    )

    with (
        patch(
            "agent_platform.server.api.private_v2.mcp_servers.call_mcp_runtime_deployment_api",
            new_callable=AsyncMock,
            return_value=mock_deployment_response,
        ),
        patch("agent_platform.server.api.private_v2.mcp_servers._sync_file_based_mcp_servers"),
    ):
        # First upload
        response1 = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )
        assert response1.status_code == 200

        # Second upload with same name
        zip_content.seek(0)
        response2 = client.post(
            "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
        )

    assert response2.status_code == 409
    response_data = response2.json()
    error_message = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "already exists" in error_message


def test_upload_mcp_server_quota_check(fastapi_app):
    """Test that upload endpoint has quota check."""
    import io
    import zipfile
    from unittest.mock import AsyncMock, patch

    from starlette.testclient import TestClient

    from agent_platform.core.errors.quotas import MCPServerQuotaExceededError
    from agent_platform.server.api.dependencies import check_mcp_server_quota
    from agent_platform.server.api.private_v2.mcp_servers import MCPRuntimeDeploymentResponse

    # Mock the quota check to raise quota exceeded error
    async def mock_quota_check_exceeded():
        raise MCPServerQuotaExceededError(current_count=3, quota_limit=2)

    fastapi_app.dependency_overrides[check_mcp_server_quota] = mock_quota_check_exceeded

    try:
        client = TestClient(fastapi_app)

        zip_content = io.BytesIO()
        with zipfile.ZipFile(zip_content, "w") as zf:
            zf.writestr("test.txt", "test content")
        zip_content.seek(0)

        files = {"file": ("test-package.zip", zip_content, "application/zip")}
        data = {"name": "test-action-server"}

        # Mock the MCP Runtime API call function (even though quota check fails first)
        mock_deployment_response = MCPRuntimeDeploymentResponse(
            url="https://deployed-mcp-server.example.com/endpoint",
            status="running",
            deployment_id="test-deployment-quota",
        )

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.call_mcp_runtime_deployment_api",
            new_callable=AsyncMock,
            return_value=mock_deployment_response,
        ):
            response = client.post(
                "/api/v2/private/mcp-servers/mcp-servers-hosted", files=files, data=data
            )

        assert response.status_code == 429
    finally:
        fastapi_app.dependency_overrides.clear()
