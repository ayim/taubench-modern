from unittest.mock import Mock, patch

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

    def test_ok_endpoint_fails_with_precondition_error(self, client: TestClient):
        """Test that the /ok endpoint fails because DIDS is not configured (stub behavior)."""
        # TODO: Update test after implementation of DIDS server
        response = client.get("/api/v2/document-intelligence/ok")

        # Expect 412 Precondition Failed because the dependency check fails
        assert response.status_code == 412

        # Check the error response structure
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.PRECONDITION_FAILED.value.code


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
