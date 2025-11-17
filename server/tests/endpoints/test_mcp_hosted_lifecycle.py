"""Tests for MCP hosted server lifecycle management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_hosted_mcp_file():
    """Mock .zip file for hosted MCP server creation."""
    return ("test-package.zip", b"fake zip content", "application/zip")


@pytest.fixture
def mock_deploy_mcp_server():
    """Mock deploy_mcp_server function."""
    with patch("agent_platform.server.api.private_v2.mcp_servers.deploy_mcp_server") as mock_deploy:
        mock_deploy.return_value = "https://runtime.example.com/deployments/test-deployment-id"
        yield mock_deploy


@pytest.fixture
def mock_delete_deployment():
    """Mock delete_deployment function."""
    with patch("agent_platform.server.api.private_v2.mcp_servers.delete_deployment") as mock_delete:
        mock_delete.return_value = True
        yield mock_delete


def test_create_hosted_mcp_server_stores_deployment_id(
    client: TestClient,
    mock_hosted_mcp_file: tuple[str, bytes, str],
    mock_deploy_mcp_server: MagicMock,
):
    """Test that creating a hosted MCP server stores the deployment_id in the database."""
    filename, content, content_type = mock_hosted_mcp_file

    response = client.post(
        "/api/v2/private/mcp-servers/mcp-servers-hosted",
        files={"file": (filename, content, content_type)},
        data={"name": "test-hosted-server"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-hosted-server"
    assert data["type"] == "sema4ai_action_server"
    assert "https://runtime.example.com/deployments/" in data["url"]

    # Verify deployment_id was stored by checking it's returned on delete
    mcp_server_id = data["mcp_server_id"]
    assert mcp_server_id is not None


def test_create_hosted_mcp_server_with_headers(
    client: TestClient,
    mock_hosted_mcp_file: tuple[str, bytes, str],
    mock_deploy_mcp_server: MagicMock,
):
    """Test creating hosted MCP server with custom headers."""
    filename, content, content_type = mock_hosted_mcp_file

    headers_json = '{"Authorization": "Bearer test-token"}'

    response = client.post(
        "/api/v2/private/mcp-servers/mcp-servers-hosted",
        files={"file": (filename, content, content_type)},
        data={"name": "test-hosted-with-headers", "headers": headers_json},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-hosted-with-headers"
    assert data["headers"] == {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_delete_hosted_mcp_server_calls_runtime_api(
    client: TestClient,
    mock_hosted_mcp_file: tuple[str, bytes, str],
    mock_deploy_mcp_server: MagicMock,
):
    """Test that deleting a hosted MCP server calls the runtime API to delete the deployment."""
    filename, content, content_type = mock_hosted_mcp_file

    # Create hosted server
    create_response = client.post(
        "/api/v2/private/mcp-servers/mcp-servers-hosted",
        files={"file": (filename, content, content_type)},
        data={"name": "test-delete-hosted"},
    )
    assert create_response.status_code == 200
    mcp_server_id = create_response.json()["mcp_server_id"]

    # Mock the delete_deployment import inside the delete endpoint
    with patch(
        "agent_platform.server.api.private_v2.mcp_servers.delete_deployment",
        new_callable=AsyncMock,
    ) as mock_delete:
        mock_delete.return_value = True

        # Delete the server
        delete_response = client.delete(f"/api/v2/private/mcp-servers/{mcp_server_id}")
        assert delete_response.status_code == 204

        # Verify runtime API was called
        mock_delete.assert_called_once()
        called_deployment_id = mock_delete.call_args[0][0]
        assert called_deployment_id is not None
        assert isinstance(called_deployment_id, str)


@pytest.mark.asyncio
async def test_delete_hosted_mcp_server_continues_on_runtime_failure(
    client: TestClient,
    mock_hosted_mcp_file: tuple[str, bytes, str],
    mock_deploy_mcp_server: MagicMock,
):
    """Test that DB deletion succeeds even if runtime API deletion fails."""
    filename, content, content_type = mock_hosted_mcp_file

    # Create hosted server
    create_response = client.post(
        "/api/v2/private/mcp-servers/mcp-servers-hosted",
        files={"file": (filename, content, content_type)},
        data={"name": "test-delete-runtime-fails"},
    )
    assert create_response.status_code == 200
    mcp_server_id = create_response.json()["mcp_server_id"]

    # Mock runtime API failure
    with patch(
        "agent_platform.server.api.private_v2.mcp_servers.delete_deployment",
        new_callable=AsyncMock,
    ) as mock_delete:
        mock_delete.return_value = False  # Simulate failure

        # Delete should still succeed
        delete_response = client.delete(f"/api/v2/private/mcp-servers/{mcp_server_id}")
        assert delete_response.status_code == 204

        # Verify runtime API was called
        mock_delete.assert_called_once()

    # Verify server is actually deleted from DB
    get_response = client.get(f"/api/v2/private/mcp-servers/{mcp_server_id}")
    assert get_response.status_code == 404


def test_delete_non_hosted_mcp_server_no_runtime_call(client: TestClient):
    """Test that deleting a non-hosted MCP server doesn't call runtime API."""
    # Create non-hosted server
    payload = {
        "name": "test-non-hosted",
        "transport": "streamable-http",
        "url": "https://external.example.com/mcp",
    }
    create_response = client.post("/api/v2/private/mcp-servers/", json=payload)
    assert create_response.status_code == 200
    mcp_server_id = create_response.json()["mcp_server_id"]

    with patch(
        "agent_platform.server.api.private_v2.mcp_servers.delete_deployment",
        new_callable=AsyncMock,
    ) as mock_delete:
        # Delete the server
        delete_response = client.delete(f"/api/v2/private/mcp-servers/{mcp_server_id}")
        assert delete_response.status_code == 204

        # Verify runtime API was NOT called
        mock_delete.assert_not_called()
