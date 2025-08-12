from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sema4ai_docint import normalize_name

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

        # Expect 412 Precondition Failed because no configuration exists in storage
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

    def test_get_all_layouts_returns_layouts(self, client: TestClient):
        """GET /document-intelligence/layouts should return layout summaries."""
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

        storage_instance = StorageService.get_instance()

        # Fake DI service and datasource
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Fake layouts returned by the model layer
        layout1 = Mock()
        layout1.name = "Invoice"
        layout1.data_model = "InvoiceModel"
        layout1.summary = "Standard invoice layout"
        layout2 = Mock()
        layout2.name = "Receipt"
        layout2.data_model = "ReceiptModel"
        layout2.summary = None

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_all",
                return_value=[layout1, layout2],
            ) as mock_find_all,
        ):
            response = client.get("/api/v2/document-intelligence/layouts")

        assert response.status_code == 200
        assert response.json() == [
            {
                "name": "Invoice",
                "data_model": "InvoiceModel",
                "summary": "Standard invoice layout",
            },
            {
                "name": "Receipt",
                "data_model": "ReceiptModel",
                "summary": None,
            },
        ]
        mock_find_all.assert_called_once()

    def test_get_all_layouts_returns_empty_list(self, client: TestClient):
        """GET /document-intelligence/layouts should return an empty list when no layouts exist."""
        valid_details = DIDSConnectionDetails(
            username="user",
            password=SecretString("pass"),
            connections=[
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                ),
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=5432, kind=DIDSConnectionKind.MYSQL
                ),
            ],
        )

        storage_instance = StorageService.get_instance()
        fake_service = Mock()
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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_all",
                return_value=[],
            ),
        ):
            response = client.get("/api/v2/document-intelligence/layouts")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_all_layouts_fails_when_dids_not_configured(self, client: TestClient):
        """When DIDS details are missing, the layouts endpoint should return precondition failed."""
        response = client.get("/api/v2/document-intelligence/layouts")

        assert response.status_code == 412
        error = response.json()["error"]
        assert error["code"] == ErrorCode.PRECONDITION_FAILED.value.code


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


class TestDataModelEndpoints:
    """Tests for data model endpoints (list, create, get, update)."""

    def _valid_details(self) -> DIDSConnectionDetails:
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

    def _sample_data_model_payload(self) -> dict:
        return {
            "dataModel": {
                "name": "invoices",
                "description": "Invoice data model",
                "schema": {"type": "object", "properties": {"id": {"type": "string"}}},
                "views": [
                    {
                        "name": "v_invoices",
                        "sql": "SELECT id FROM invoices",
                        "columns": [{"name": "id", "type": "string"}],
                    }
                ],
                "qualityChecks": [
                    {"name": "non_empty_id", "query": "SELECT ...", "description": "no empty id"}
                ],
                "prompt": "extract invoices",
                "summary": "Invoices model",
            }
        }

    def _sample_data_model_dict(self) -> dict:
        return {
            "name": "invoices",
            "description": "Invoice data model",
            "model_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
            "views": [
                {
                    "name": "v_invoices",
                    "sql": "SELECT id FROM invoices",
                    "columns": [{"name": "id", "type": "string"}],
                }
            ],
            "quality_checks": [
                {"name": "non_empty_id", "query": "SELECT ...", "description": "no empty id"}
            ],
            "prompt": "extract invoices",
            "summary": "Invoices model",
        }

    def test_list_data_models_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        sample_models = [
            SimpleNamespace(
                name="invoices", description="Invoice data model", model_schema={"type": "object"}
            ),
            SimpleNamespace(name="receipts", description="Receipts", model_schema={}),
        ]

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_all",
                return_value=sample_models,
            ) as mocked_find_all,
        ):
            resp = client.get("/api/v2/document-intelligence/data-models")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        assert {m["name"] for m in body} == {"invoices", "receipts"}
        # summaries should not include heavy fields
        assert "views" not in body[0]
        assert "quality_checks" not in body[0]
        mocked_find_all.assert_called_once()

    def test_create_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.insert",
                return_value=None,
            ) as mocked_insert,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                side_effect=[None, SimpleNamespace(**self._sample_data_model_dict())],
            ) as mocked_find_by_name,
        ):
            resp = client.post("/api/v2/document-intelligence/data-models", json=payload)

        assert resp.status_code == 201
        body = resp.json()
        assert body["dataModel"]["name"] == "invoices"
        assert body["dataModel"]["schema"]["type"] == "object"
        mocked_insert.assert_called_once()
        mocked_find_by_name.assert_called()

    def test_create_data_model_failure_when_not_found_after_insert(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.insert",
                return_value=None,
            ),
            # This patch is to simulate the case of an internal error when the model is not
            # found right after creation.
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.post("/api/v2/document-intelligence/data-models", json=payload)

        assert resp.status_code == 500
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.UNEXPECTED.value.code

    def test_get_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(**self._sample_data_model_dict()),
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/data-models/invoices")

        assert resp.status_code == 200
        assert resp.json()["dataModel"]["name"] == "invoices"

    def test_get_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/data-models/missing")

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_update_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_update_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(**self._sample_data_model_dict(), update=Mock()),
            ) as mocked_find_by_name,
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        # Ensure update was invoked on the returned instance
        instance = mocked_find_by_name.return_value
        instance.update.assert_called_once()

    def test_delete_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.delete("/api/v2/document-intelligence/data-models/missing")

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_delete_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        sample_model = self._sample_data_model_dict()

        class DummyDM:
            def __init__(self, data):
                self.__dict__.update(data)

            def delete(self, _ds):
                return True

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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=DummyDM(sample_model),
            ),
        ):
            resp = client.delete("/api/v2/document-intelligence/data-models/invoices")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestUpsertLayout:
    def _valid_details(self) -> DIDSConnectionDetails:
        return DIDSConnectionDetails(
            username="user",
            password=SecretString("pass"),
            connections=[
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=47334, kind=DIDSConnectionKind.HTTP
                ),
                DIDSApiConnectionDetails(
                    host="127.0.0.1", port=5432, kind=DIDSConnectionKind.MYSQL
                ),
            ],
        )

    def test_upsert_layout_inserts_when_not_exists(self, client: TestClient):
        payload = {
            "name": "invoice-v1",
            "dataModelName": "invoice",
            "extractionSchema": {"type": "object"},
            "translationSchema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Invoice layout",
            "extractionConfig": {"threshold": 0.8},
            "prompt": "You are a helpful layout model.",
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance"
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=None,
            ) as find_by_name,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.insert"
            ) as insert,
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.post("/api/v2/document-intelligence/layouts", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        find_by_name.assert_called_once()
        insert.assert_called_once()

    def test_upsert_layout_updates_when_exists(self, client: TestClient):
        payload = {
            "name": "invoice-v1",
            "dataModelName": "invoice",
            "extractionSchema": {"type": "object"},
            "translationSchema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Invoice layout",
            "extractionConfig": {"threshold": 0.8},
            "prompt": "You are a helpful layout model.",
        }

        expected_wrapped = {
            "rules": [{"mode": "rename", "source": "total", "target": "grand_total"}]
        }

        storage_instance = StorageService.get_instance()
        existing_layout = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=existing_layout,
            ) as find_by_name,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.insert",
            ) as insert,
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            with patch.object(existing_layout, "update") as update:
                response = client.post("/api/v2/document-intelligence/layouts", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        find_by_name.assert_called_once()
        update.assert_called_once()
        insert.assert_not_called()
        assert existing_layout.extraction_schema == {"type": "object"}
        assert existing_layout.translation_schema == expected_wrapped
        assert existing_layout.summary == "Invoice layout"
        assert existing_layout.extraction_config == {"threshold": 0.8}
        assert existing_layout.system_prompt == "You are a helpful layout model."

    def test_upsert_layout_normalizes_names_on_lookup(self, client: TestClient):
        payload = {
            "name": "Invoice Layout V1!!",
            "dataModelName": "Koch Invoices",
            "extractionSchema": {"type": "object"},
            "translationSchema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
        }

        storage_instance = StorageService.get_instance()
        existing_layout = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=existing_layout,
            ) as find_by_name,
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            with patch.object(existing_layout, "update") as update:
                response = client.post("/api/v2/document-intelligence/layouts", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        # Ensure lookup used normalized names
        expected_dm = normalize_name(payload["dataModelName"])  # type: ignore[index]
        expected_name = normalize_name(payload["name"])  # type: ignore[index]
        find_by_name.assert_called_once_with(ANY, expected_dm, expected_name)
        update.assert_called_once()

    def test_upsert_layout_inserts_with_normalized_name(self, client: TestClient):
        payload = {
            "name": "Invoice Layout V1!!",
            "dataModelName": "Koch Invoices",
            "extractionSchema": {"type": "object"},
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=None,
            ) as find_by_name,
            patch(
                "agent_platform.core.payloads.upsert_document_layout.DocumentLayout",
            ) as dummy_dl,
        ):
            # Configure a simple dummy DocumentLayout class to capture instance attributes
            class _DummyDL:
                last_instance = None

                def __init__(self, name, data_model, **kwargs):
                    self.name = name
                    self.data_model = data_model
                    # Optionally capture expected attributes if provided
                    self.extraction_schema = kwargs.get("extraction_schema")
                    self.translation_schema = kwargs.get("translation_schema")
                    self.summary = kwargs.get("summary")
                    self.extraction_config = kwargs.get("extraction_config")
                    self.system_prompt = kwargs.get("system_prompt")
                    _DummyDL.last_instance = self

                def insert(self, ds):
                    return None

            dummy_dl.side_effect = _DummyDL

            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.post("/api/v2/document-intelligence/layouts", json=payload)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        find_by_name.assert_called_once()
        # Ensure the created layout instance had normalized name
        created_layout = dummy_dl.side_effect.last_instance  # type: ignore[attr-defined]
        assert created_layout is not None
        assert created_layout.name == normalize_name(payload["name"])  # type: ignore[index]
