from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.document_intelligence.dataserver import (
    DIDSApiConnectionDetails,
    DIDSConnectionDetails,
    DIDSConnectionKind,
)
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.utils import SecretString
from agent_platform.server.api.private_v2 import document_intelligence
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage.option import StorageService


@pytest.fixture
def test_user(stub_user):
    """Use the stub user from conftest."""
    return stub_user


@pytest.fixture
def fastapi_app(storage, test_user) -> FastAPI:
    """FastAPI app configured with document intelligence router for testing."""
    StorageService.reset()
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(document_intelligence.router, prefix="/api/v2/document-intelligence")
    app.dependency_overrides[auth_user] = lambda: test_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)


class TestDocumentIntelligenceEndpoints:
    """Tests for document intelligence endpoints."""

    def test_ok_endpoint_fails_when_dids_not_configured(self, client: TestClient):
        """When no DIDS details exist, dependency should fail early with a platform error."""
        response = client.get("/api/v2/document-intelligence/ok")

        # Expect 500 Unexpected because no configuration exists in storage
        assert response.status_code == 412

        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.PRECONDITION_FAILED.value.code
        assert (
            error_data["error"]["message"]
            == "Document Intelligence DataServer has not been configured"
        )

    def test_ok_endpoint_succeeds_when_configured(self, client: TestClient):
        """When DIDS details are present and valid, the endpoint should succeed."""
        # Prepare valid connection details
        valid_details = DIDSConnectionDetails(
            username="testuser",
            password=SecretString("testpass"),
            connections=[
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                ),
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=5432, kind=DIDSConnectionKind.MYSQL
                ),
            ],
        )

        # Patch the storage instance used by the router dependency to return valid details
        storage_instance = StorageService.get_instance()

        # Stub the DI service to avoid touching real DataSource during dependency execution
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=valid_details),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_upsert_document_intelligence_succeeds(self, client: TestClient):
        """POST /document-intelligence should persist details, integrations,
        and build datasource.
        """
        payload = {
            "integrations": [
                {
                    "type": "reducto",
                    "endpoint": "https://reducto.example.com",
                    "api_key": "secret-key",
                }
            ],
            "data_server": {
                "credentials": {"username": "user", "password": "pass"},
                "api": {
                    "http": {"url": "127.0.0.1", "port": 47334},
                    "mysql": {"host": "127.0.0.1", "port": 5432},
                },
            },
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "set_dids_connection_details",
                new=AsyncMock(),
            ) as set_details,
            patch.object(
                storage_instance,
                "set_document_intelligence_integration",
                new=AsyncMock(),
            ) as set_integration,
            patch.object(document_intelligence, "_build_datasource", new=AsyncMock()) as build_ds,
        ):
            response = client.post("/api/v2/document-intelligence", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        set_details.assert_awaited()
        set_integration.assert_awaited()
        build_ds.assert_awaited()

    @pytest.mark.parametrize(
        ("details", "expected_substring"),
        [
            (
                DIDSConnectionDetails(
                    username=None,
                    password=SecretString("testpass"),
                    connections=[
                        DIDSApiConnectionDetails(
                            host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                        ),
                    ],
                ),
                "missing username",
            ),
            (
                DIDSConnectionDetails(
                    username="   ",
                    password=SecretString("testpass"),
                    connections=[
                        DIDSApiConnectionDetails(
                            host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                        ),
                    ],
                ),
                "missing username",
            ),
            (
                DIDSConnectionDetails(
                    username="user",
                    password=None,
                    connections=[
                        DIDSApiConnectionDetails(
                            host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                        ),
                    ],
                ),
                "missing password",
            ),
            (
                DIDSConnectionDetails(
                    username="user",
                    password=SecretString("   "),
                    connections=[
                        DIDSApiConnectionDetails(
                            host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                        ),
                    ],
                ),
                "missing password",
            ),
            (
                DIDSConnectionDetails(
                    username="user",
                    password=SecretString("testpass"),
                    connections=[],
                ),
                "missing connections",
            ),
        ],
    )
    def test_ok_endpoint_fails_with_partial_configuration(
        self, client: TestClient, details: DIDSConnectionDetails, expected_substring: str
    ):
        """Ensure dependency validation catches partial configurations with clear messages."""
        storage_instance = StorageService.get_instance()
        with patch.object(
            storage_instance, "get_dids_connection_details", new=AsyncMock(return_value=details)
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 412
        error = response.json()["error"]
        assert error["code"] == ErrorCode.PRECONDITION_FAILED.value.code
        assert expected_substring in error["message"]


class TestBuildDatasource:
    """Tests for the _build_datasource function."""

    @pytest.fixture
    def sample_connection_details(self):
        """Sample DIDSConnectionDetails instance for testing."""
        return DIDSConnectionDetails(
            username="testuser",
            password=SecretString("testpass"),
            connections=[
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                ),
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=5432, kind=DIDSConnectionKind.MYSQL
                ),
            ],
        )

    @patch("agent_platform.server.api.private_v2.document_intelligence.PostgresConfig")
    @patch("agent_platform.server.api.private_v2.document_intelligence.DataSource")
    @patch("agent_platform.server.api.private_v2.document_intelligence.initialize_database")
    async def test_build_datasource_success(
        self, mock_initialize_db, mock_datasource, mock_postgres_config, sample_connection_details
    ):
        """Test successful datasource creation and initialization."""
        # Setup PostgresConfig mock
        mock_postgres_instance = Mock()
        mock_postgres_instance.user = "testuser"
        mock_postgres_instance.password = "testpass"
        mock_postgres_instance.host = "localhost"
        mock_postgres_instance.port = 5432
        mock_postgres_instance.db = "testdb"
        mock_postgres_config.get_instance.return_value = mock_postgres_instance

        # Setup DataSource mocks
        mock_admin_ds = Mock()
        mock_connection = Mock()
        mock_source_info = Mock()
        mock_source_info.name = "existing_source"
        mock_connection.list_data_sources.return_value = [mock_source_info]
        mock_admin_ds.connection.return_value = mock_connection
        mock_admin_ds.execute_sql.return_value = None

        mock_docint_ds = Mock()

        # Configure DataSource.model_validate to return different instances
        mock_datasource.model_validate.side_effect = [mock_admin_ds, mock_docint_ds]

        # Call the function
        await document_intelligence._build_datasource(sample_connection_details)

        # Verify DataSource.setup_connection_from_input_json was called
        mock_datasource.setup_connection_from_input_json.assert_called_once()

        # Verify proper_json structure (from dataclass as_datasource_connection_input method)
        call_args = mock_datasource.setup_connection_from_input_json.call_args[0][0]
        assert call_args["http"]["url"] == "127.0.0.1:47334"
        assert call_args["http"]["user"] == "testuser"
        assert call_args["http"]["password"] == "testpass"
        assert call_args["mysql"]["host"] == "127.0.0.1"
        assert call_args["mysql"]["port"] == 5432
        assert call_args["mysql"]["user"] == "testuser"
        assert call_args["mysql"]["password"] == "testpass"

        # Verify admin datasource was created with correct name
        assert mock_datasource.model_validate.call_count == 2
        mock_datasource.model_validate.assert_any_call(datasource_name="sema4ai")
        mock_datasource.model_validate.assert_any_call(datasource_name="DocumentIntelligence")

        # Verify database operations
        mock_admin_ds.execute_sql.assert_any_call("DROP DATABASE IF EXISTS DocumentIntelligence;")
        assert mock_admin_ds.execute_sql.call_count == 2  # DROP and CREATE

        # Verify initialize_database was called
        mock_initialize_db.assert_called_once_with("postgres", mock_docint_ds)

    @patch("agent_platform.server.api.private_v2.document_intelligence.PostgresConfig")
    @patch("agent_platform.server.api.private_v2.document_intelligence.DataSource")
    async def test_build_datasource_connection_error(
        self, mock_datasource, mock_postgres_config, sample_connection_details
    ):
        """Test error handling when connection setup fails."""
        # Setup PostgresConfig mock
        mock_postgres_instance = Mock()
        mock_postgres_instance.user = "testuser"
        mock_postgres_instance.password = "testpass"
        mock_postgres_instance.host = "localhost"
        mock_postgres_instance.port = 5432
        mock_postgres_instance.db = "testdb"
        mock_postgres_config.get_instance.return_value = mock_postgres_instance

        # Setup mock to raise exception on setup
        mock_datasource.setup_connection_from_input_json.side_effect = Exception(
            "Connection failed"
        )

        # Verify PlatformError is raised
        with pytest.raises(PlatformError) as exc_info:
            await document_intelligence._build_datasource(sample_connection_details)

        assert exc_info.value.response.error_code == ErrorCode.UNEXPECTED
        assert "Error initializing Document Intelligence database" in str(exc_info.value)

    @patch("agent_platform.server.api.private_v2.document_intelligence.PostgresConfig")
    @patch("agent_platform.server.api.private_v2.document_intelligence.DataSource")
    async def test_build_datasource_uses_postgres_config(
        self, mock_datasource, mock_postgres_config, sample_connection_details
    ):
        """Test that the function correctly uses PostgresConfig for database connection details."""
        # Setup PostgresConfig mock with class attributes
        mock_postgres_config.user = "config_user"
        mock_postgres_config.password = "config_pass"
        mock_postgres_config.host = "config_host"
        mock_postgres_config.port = 5433
        mock_postgres_config.db = "config_db"

        # Setup DataSource mocks
        mock_admin_ds = Mock()
        mock_docint_ds = Mock()
        mock_datasource.model_validate.side_effect = [mock_admin_ds, mock_docint_ds]

        # Call the function
        await document_intelligence._build_datasource(sample_connection_details)
        # Verify the CREATE DATABASE SQL includes the PostgresConfig values
        create_sql_call = None
        for call in mock_admin_ds.execute_sql.call_args_list:
            sql = call[0][0]
            if "CREATE DATABASE DocumentIntelligence" in sql:
                create_sql_call = sql
                break

        assert create_sql_call is not None
        assert '"user": "config_user"' in create_sql_call
        assert '"password": "config_pass"' in create_sql_call
        assert '"host": "config_host"' in create_sql_call
        assert '"port": 5433' in create_sql_call
        assert '"database": "config_db"' in create_sql_call
