from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.configurations.config_validation import ConfigType
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.server.api.private_v2 import config
from agent_platform.server.auth.handlers import User, auth_user
from agent_platform.server.storage.option import StorageService


@pytest.fixture
def test_user():
    """Test user for authentication."""
    return User(user_id="test-user-123", sub="test_sub")


@pytest.fixture
def mock_storage():
    """Mock storage with config operations."""
    storage = AsyncMock()
    storage.set_config = AsyncMock()
    storage.list_all_configs = AsyncMock()
    return storage


@pytest.fixture
def mock_quotas_service():
    """Mock QuotasService with all quota operations."""
    # Use regular Mock for the service instance since get_all_configs is sync
    service = Mock()

    # Mock the sync get_all_configs method
    service.get_all_configs.return_value = {
        "MAX_AGENTS": {
            "storage_key": "MAX_AGENTS",
            "value": 100,
            "description": "Maximum number of agents",
        },
        "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB": {
            "storage_key": "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB",
            "value": 100,
            "description": "Maximum work item payload size",
        },
        "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB": {
            "storage_key": "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB",
            "value": 100,
            "description": "Maximum file attachment size",
        },
        "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS": {
            "storage_key": "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS",
            "value": 10,
            "description": "Maximum parallel work items",
        },
        "MAX_MCP_SERVERS_IN_AGENT": {
            "storage_key": "MAX_MCP_SERVERS_IN_AGENT",
            "value": 30,
            "description": "Maximum MCP servers per agent",
        },
        "POSTGRES_POOL_MAX_SIZE": {
            "storage_key": "POSTGRES_POOL_MAX_SIZE",
            "value": 50,
            "description": "Maximum connection pool size (applies to Psycopg/SQLAlchemy)",
        },
    }

    # Mock the async set_config method
    service.set_config = AsyncMock()
    return service


@pytest.fixture
def client(test_user, mock_storage, mock_quotas_service):
    """Test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(config.router, prefix="/api/v2/private/config")

    # Override dependencies using the correct functions
    app.dependency_overrides[StorageService.get_instance] = lambda: mock_storage
    app.dependency_overrides[auth_user] = lambda: test_user

    # Use patch to mock QuotasService.get_instance() - return the mock service directly
    async def mock_get_instance():
        return mock_quotas_service

    with patch(
        "agent_platform.server.api.private_v2.config.QuotasService.get_instance",
        side_effect=mock_get_instance,
    ):
        yield TestClient(app)


class TestSetConfigEndpoint:
    """Tests for the POST /config/ endpoint."""

    def test_set_config_success(self, client: TestClient, mock_quotas_service):
        """Test successfully setting a configuration value."""
        payload = {"config_type": "MAX_AGENTS", "current_value": "50"}

        response = client.post("/api/v2/private/config/", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Configuration set successfully"
        assert data["config_type"] == "MAX_AGENTS"

        # Verify QuotasService was called correctly
        mock_quotas_service.set_config.assert_called_once_with("MAX_AGENTS", "50")

    def test_set_config_invalid_config_type(self, client: TestClient, mock_storage):
        """Test setting a configuration with invalid config_type."""
        payload = {"config_type": "INVALID_CONFIG", "current_value": "100"}

        response = client.post("/api/v2/private/config/", json=payload)

        # With strict ConfigType typing, FastAPI validates at Pydantic level (422)
        assert response.status_code == 422
        response_data = response.json()
        assert "detail" in response_data
        # FastAPI validation error format
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) > 0
        assert "config_type" in str(response_data["detail"])

    def test_set_config_unknown_quota_name(self, client: TestClient, mock_quotas_service):
        """Test setting a config_type that causes an exception in QuotasService."""
        # Mock set_config to raise a PlatformHTTPError (unknown config type)
        mock_quotas_service.set_config.side_effect = PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Unknown config type: MAX_AGENTS",
        )

        payload = {"config_type": "MAX_AGENTS", "current_value": "100"}

        # The endpoint should throw a PlatformHTTPError
        with pytest.raises(PlatformHTTPError):
            client.post("/api/v2/private/config/", json=payload)

        # Reset the side_effect to avoid affecting other tests
        mock_quotas_service.set_config.side_effect = None

    def test_set_config_all_valid_config_types(self, client: TestClient, mock_quotas_service):
        """Test that all defined config types are accepted."""
        for config_type in ConfigType:
            payload = {"config_type": config_type, "current_value": "100"}

            response = client.post("/api/v2/private/config/", json=payload)

            assert response.status_code == 200

    def test_set_config_string_values_accepted(self, client: TestClient, mock_quotas_service):
        """Test that various string values are accepted for current_value."""
        test_values = ["100", "0", "999999", "custom_value", "true", "false"]

        for value in test_values:
            payload = {"config_type": "MAX_AGENTS", "current_value": value}

            response = client.post("/api/v2/private/config/", json=payload)

            assert response.status_code == 200

    def test_set_config_missing_fields_validation(self, client: TestClient, mock_storage):
        """Test that missing required fields return proper validation errors."""
        # Missing current_value
        payload = {"config_type": "MAX_AGENTS"}
        response = client.post("/api/v2/private/config/", json=payload)
        assert response.status_code == 422

        # Missing config_type
        payload = {"current_value": "100"}
        response = client.post("/api/v2/private/config/", json=payload)
        assert response.status_code == 422

        # Empty payload
        response = client.post("/api/v2/private/config/", json={})
        assert response.status_code == 422


class TestGetAllConfigsEndpoint:
    """Tests for the GET /config/ endpoint."""

    def test_get_all_configs_success(self, client: TestClient, mock_quotas_service):
        """Test successfully retrieving all configurations from QuotasService."""
        response = client.get("/api/v2/private/config/")

        assert response.status_code == 200
        data = response.json()

        # Should return all quotas from QuotasService
        assert len(data) == 6

        # Verify structure of returned data
        config_types = {item["config_type"] for item in data}
        expected_config_types = {
            "MAX_AGENTS",
            "MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB",
            "MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB",
            "MAX_PARALLEL_WORK_ITEMS_IN_PROCESS",
            "MAX_MCP_SERVERS_IN_AGENT",
            "POSTGRES_POOL_MAX_SIZE",
        }
        assert config_types == expected_config_types

        # Verify each item has required fields (ConfigResponse structure)
        for item in data:
            assert "config_type" in item
            assert "config_value" in item
            # ConfigResponse only has config_type and config_value

    def test_get_all_configs_empty_quotas_service(self, client: TestClient, mock_quotas_service):
        """Test retrieving configs when QuotasService returns empty."""
        mock_quotas_service.get_all_configs.return_value = {}

        response = client.get("/api/v2/private/config/")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestConfigValidationIntegration:
    """Integration tests for config validation."""

    def test_validation_error_format(self, client: TestClient, mock_storage):
        """Test that validation errors return proper format and status codes."""
        payload = {"config_type": "DEFINITELY_INVALID", "current_value": "100"}

        response = client.post("/api/v2/private/config/", json=payload)

        # With strict ConfigType typing, FastAPI validates at Pydantic level (422)
        assert response.status_code == 422
        response_data = response.json()
        assert "detail" in response_data
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) > 0

    def test_pydantic_validation_for_invalid_field_types(self, client: TestClient, mock_storage):
        """Test FastAPI's built-in validation for incorrect field types."""
        # Test with non-string values that should be strings
        invalid_payloads = [
            {"config_type": 123, "current_value": "100"},  # config_type as int
            {"config_type": "MAX_AGENTS", "current_value": 123},  # current_value as int
        ]

        for payload in invalid_payloads:
            response = client.post("/api/v2/private/config/", json=payload)
            assert response.status_code == 422  # FastAPI validation error
