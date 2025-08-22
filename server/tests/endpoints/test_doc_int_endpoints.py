from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reducto.types.shared.bounding_box import BoundingBox
from reducto.types.shared.parse_response import (
    ParseResponse,
    ResultFullResult,
    ResultFullResultChunk,
    ResultFullResultChunkBlock,
)
from reducto.types.shared.parse_usage import ParseUsage
from sema4ai.data._data_source import ConnectionNotSetupError
from sema4ai_docint import normalize_name
from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
)
from sema4ai_docint.models.constants import DATA_SOURCE_NAME

from agent_platform.core.data_server.data_connection import (
    DataConnection,
    DataConnectionEngine,
)
from agent_platform.core.data_server.data_server import (
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.data_server.data_sources import DataSources
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import (
    get_agent_server_client,
    get_file_manager,
)
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


@pytest.fixture
def mock_docint_service() -> Mock:
    """Create a mock DocumentIntelligenceService with proper connection structure."""
    fake_service = Mock()
    fake_service.ensure_setup.return_value = None

    # Mock datasource with connection structure for connectivity check
    fake_datasource = Mock()
    fake_connection = Mock()
    fake_http_connection = Mock()
    fake_http_connection.login.return_value = None  # Successful login by default
    fake_connection._http_connection = fake_http_connection
    fake_datasource.connection.return_value = fake_connection
    fake_service.get_docint_datasource.return_value = fake_datasource

    return fake_service


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

    def test_ok_endpoint_succeeds_when_configured(
        self, client: TestClient, mock_docint_service: Mock
    ):
        """When DIDS details are present and valid, the endpoint should succeed."""
        # Prepare valid connection details
        valid_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        # Patch the storage instance used by the router dependency to return valid details
        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=valid_details),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=mock_docint_service,
            ),
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_ok_endpoint_fails_when_data_server_offline(
        self, client: TestClient, mock_docint_service: Mock
    ):
        """When DIDS details are valid but data server is unreachable, should return 412."""
        valid_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        storage_instance = StorageService.get_instance()

        # Create mock service and customize it to make login fail (simulate offline server)
        datasource = mock_docint_service.get_docint_datasource.return_value
        http_conn = datasource.connection.return_value._http_connection
        http_conn.login.side_effect = Exception("Connection refused")

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=valid_details),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=mock_docint_service,
            ),
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 412
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.PRECONDITION_FAILED.value.code
        expected_msg = "Failed to login to Document Intelligence data source: Connection refused"
        assert expected_msg in error_data["error"]["message"]

    def test_ok_endpoint_fails_when_connection_not_setup(
        self, client: TestClient, mock_docint_service: Mock
    ):
        """When datasource connection is not properly setup, should return 412."""
        valid_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        storage_instance = StorageService.get_instance()

        # Create mock service and customize it to make connection() raise ConnectionNotSetupError
        datasource = mock_docint_service.get_docint_datasource.return_value
        datasource.connection.side_effect = ConnectionNotSetupError("Connection not setup")

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=valid_details),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=mock_docint_service,
            ),
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 412
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.PRECONDITION_FAILED.value.code
        expected_msg = "Document Intelligence datasource connection not properly configured"
        assert expected_msg in error_data["error"]["message"]

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

    async def test_delete_di_when_not_configured(self, client: TestClient):
        """
        DELETE /document-intelligence should drop the mindsdb database and clear the
        internal state
        """
        response = client.delete("/api/v2/document-intelligence")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_delete_document_intelligence(self, client: TestClient):
        """
        DELETE /document-intelligence should drop the mindsdb database and clear the
        internal state
        """
        with patch(
            "agent_platform.server.api.private_v2.document_intelligence.DataSource"
        ) as mock_datasource:
            # Setup DataSource mocks
            mock_admin_ds = MagicMock()
            mock_admin_ds.execute_sql.return_value = None

            # Configure DataSource.model_validate to return different instances
            mock_datasource.model_validate.side_effect = [mock_admin_ds]

            storage_instance = StorageService.get_instance()

            with (
                # Inject  the DocIntDataSource
                patch.object(
                    storage_instance,
                    "get_dids_connection_details",
                    new=AsyncMock(),
                ),
                patch.object(
                    storage_instance,
                    "delete_dids_connection_details",
                    new=AsyncMock(),
                ) as delete_ds_details,
                patch.object(
                    storage_instance,
                    "delete_document_intelligence_integration",
                    new=AsyncMock(),
                ) as delete_integration,
            ):
                response = client.delete("/api/v2/document-intelligence")

            assert response.status_code == 200
            assert response.json() == {"ok": True}
            # Verify we dropped the database in mindsdb
            mock_admin_ds.execute_sql.assert_called_once_with(
                "DROP DATABASE IF EXISTS DocumentIntelligence;"
            )
            delete_integration.assert_awaited_once_with("reducto")
            delete_ds_details.assert_awaited_once()

            # Verify DataSource.setup_connection_from_input_json was called
            mock_datasource.setup_connection_from_input_json.assert_called_once()

    @pytest.mark.parametrize(
        ("details", "expected_substring"),
        [
            (
                DataServerDetails(
                    username=None,
                    password=SecretString("testpass"),
                    data_server_endpoints=[
                        DataServerEndpoint(
                            host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                        ),
                    ],
                ),
                "missing username",
            ),
            (
                DataServerDetails(
                    username="   ",
                    password=SecretString("testpass"),
                    data_server_endpoints=[
                        DataServerEndpoint(
                            host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                        ),
                    ],
                ),
                "missing username",
            ),
            (
                DataServerDetails(
                    username="user",
                    password=None,
                    data_server_endpoints=[
                        DataServerEndpoint(
                            host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                        ),
                    ],
                ),
                "missing password",
            ),
            (
                DataServerDetails(
                    username="user",
                    password=SecretString("   "),
                    data_server_endpoints=[
                        DataServerEndpoint(
                            host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                        ),
                    ],
                ),
                "missing password",
            ),
            (
                DataServerDetails(
                    username="user",
                    password=SecretString("testpass"),
                    data_server_endpoints=[],
                ),
                "missing connections",
            ),
        ],
    )
    def test_ok_endpoint_fails_with_partial_configuration(
        self, client: TestClient, details: DataServerDetails, expected_substring: str
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
        valid_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
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
        valid_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
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
    def sample_data_sources(self):
        """Sample DataSources instance for testing."""
        return DataSources(
            data_server=DataServerDetails(
                username="testuser",
                password=SecretString("testpass"),
                data_server_endpoints=[
                    DataServerEndpoint(
                        host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                    ),
                    DataServerEndpoint(
                        host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL
                    ),
                ],
            ),
            data_sources={
                DATA_SOURCE_NAME: DataConnection(
                    id="123",
                    name="docint-postgres",
                    engine=DataConnectionEngine.POSTGRES,
                    configuration={
                        "user": "testuser",
                        "password": "testpass",
                        "host": "localhost",
                        "port": 5432,
                        "database": "testdb",
                    },
                ),
            },
        )

    @patch("agent_platform.server.api.private_v2.document_intelligence.DataSource")
    @patch("agent_platform.server.api.private_v2.document_intelligence.initialize_database")
    @patch("agent_platform.server.api.private_v2.document_intelligence.initialize_data_source")
    async def test_build_datasource_success(
        self,
        mock_initialize_data_source,
        mock_initialize_database,
        mock_datasource,
        sample_data_sources,
    ):
        """Test successful datasource creation and initialization."""
        # Setup DataSource mock instance returned by model_validate
        mock_docint_ds = Mock()
        mock_datasource.model_validate.return_value = mock_docint_ds

        # Call the function
        await document_intelligence._build_datasource(sample_data_sources)

        mock_initialize_data_source.assert_awaited_once_with(sample_data_sources)

        # Verify admin datasource was created with correct name
        assert mock_datasource.model_validate.call_count == 1
        mock_datasource.model_validate.assert_any_call(datasource_name="DocumentIntelligence")

        # Verify initialize_database was called
        mock_initialize_database.assert_called_once_with("postgres", mock_docint_ds)

    @patch("agent_platform.server.api.private_v2.document_intelligence.initialize_data_source")
    async def test_build_datasource_connection_error(
        self, mock_initialize_data_source, sample_data_sources
    ):
        """Test error handling when connection setup fails."""
        # Setup mock to raise exception on setup
        mock_initialize_data_source.side_effect = Exception("Connection failed")

        # Verify PlatformError is raised
        with pytest.raises(PlatformError) as exc_info:
            await document_intelligence._build_datasource(sample_data_sources)

        assert exc_info.value.response.error_code == ErrorCode.UNEXPECTED
        assert "Error initializing Document Intelligence database" in str(exc_info.value)


class TestDataModelEndpoints:
    """Tests for data model endpoints (list, create, get, update)."""

    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
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
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.upsert_layout",
                return_value={"ok": True},
            ) as mocked_upsert_layout,
        ):
            resp = client.post("/api/v2/document-intelligence/data-models", json=payload)

        assert resp.status_code == 201
        body = resp.json()
        assert body["dataModel"]["name"] == "invoices"
        assert body["dataModel"]["schema"]["type"] == "object"
        mocked_insert.assert_called_once()
        mocked_find_by_name.assert_called()
        mocked_upsert_layout.assert_called_once()

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

    def test_update_data_model_quality_checks_only(self, client: TestClient):
        """Update only quality checks without touching other fields."""
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Existing model with baseline values
        existing_model = self._sample_data_model_dict()
        existing_instance = SimpleNamespace(**existing_model, update=Mock())

        new_quality_checks = [
            {
                "name": "check_total",
                "query": "SELECT total FROM invoices WHERE total > 0",
                "description": "Check positive totals",
            },
            {
                "name": "check_date",
                "query": "SELECT date FROM invoices WHERE date IS NOT NULL",
                "description": "Check date presence",
            },
        ]

        payload = {"dataModel": {"qualityChecks": new_quality_checks}}

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
                return_value=existing_instance,
            ) as mocked_find_by_name,
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        instance = mocked_find_by_name.return_value
        instance.update.assert_called_once()

        # Only quality_checks should change
        assert instance.quality_checks == new_quality_checks
        assert instance.description == existing_model["description"]
        assert instance.model_schema == existing_model["model_schema"]
        assert instance.views == existing_model["views"]
        assert instance.prompt == existing_model["prompt"]
        assert instance.summary == existing_model["summary"]

    def test_update_data_model_inserts_quality_checks_when_empty(self, client: TestClient):
        """Insert quality checks when the existing model has none."""
        storage_instance = StorageService.get_instance()
        valid_details = self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Existing model with empty quality checks
        existing_model = self._sample_data_model_dict()
        existing_model["quality_checks"] = []
        existing_instance = SimpleNamespace(**existing_model, update=Mock())

        inserted_quality_checks = [
            {"name": "no_empty_id", "query": "SELECT ...", "description": "no empty id"}
        ]

        # Only provide qualityChecks in the payload
        payload = {"dataModel": {"qualityChecks": inserted_quality_checks}}

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
                return_value=existing_instance,
            ) as mocked_find_by_name,
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        instance = mocked_find_by_name.return_value
        instance.update.assert_called_once()
        assert instance.quality_checks == inserted_quality_checks

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
    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

    def test_upsert_layout_inserts_when_not_exists(self, client: TestClient):
        payload = {
            "name": "invoice-v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object"},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Invoice layout",
            "extraction_config": {"threshold": 0.8},
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
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object"},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Invoice layout",
            "extraction_config": {"threshold": 0.8},
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
            "data_model_name": "Koch Invoices",
            "extraction_schema": {"type": "object"},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
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
        expected_dm = normalize_name(payload["data_model_name"])  # type: ignore[index]
        expected_name = normalize_name(payload["name"])  # type: ignore[index]
        find_by_name.assert_called_once_with(ANY, expected_dm, expected_name)
        update.assert_called_once()

    def test_upsert_layout_inserts_with_normalized_name(self, client: TestClient):
        payload = {
            "name": "Invoice Layout V1!!",
            "data_model_name": "Koch Invoices",
            "extraction_schema": {"type": "object"},
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

    def test_upsert_layout_reraises_platform_http_error(self, client: TestClient):
        """Test that PlatformHTTPError from underlying components is reraised without
        modification."""
        payload = {
            "name": "invoice-v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object"},
        }

        # Create a specific PlatformHTTPError to test with
        platform_error = PlatformHTTPError(ErrorCode.BAD_REQUEST, "Invalid schema format")

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
                side_effect=platform_error,
            ) as find_by_name,
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.post("/api/v2/document-intelligence/layouts", json=payload)

        # Verify that the PlatformHTTPError is reraised without modification
        assert response.status_code == 400  # ErrorCode.BAD_REQUEST status
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.BAD_REQUEST.value.code
        assert error_data["error"]["message"] == "Invalid schema format"
        find_by_name.assert_called_once()


class TestGetLayout:
    """Tests for the get_layout endpoint."""

    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                )
            ],
        )

    def test_get_layout_success(self, client: TestClient):
        """Test successful layout retrieval."""
        storage_instance = StorageService.get_instance()

        # Mock data that represents a DocumentLayout from the database
        mock_document_layout = SimpleNamespace(
            name="test_layout",
            data_model="test_model",
            summary="Test layout summary",
            extraction_schema={"type": "object", "properties": {"field1": {"type": "string"}}},
            translation_schema={"rules": [{"source": "field1", "target": "output_field1"}]},
            extraction_config={"mode": "strict"},
            system_prompt="Custom system prompt",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
        )

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=mock_document_layout,
            ) as mock_find,
        ):
            resp = client.get(
                "/api/v2/document-intelligence/layouts/test_layout",
                params={"data_model_name": "test_model"},
            )

        assert resp.status_code == 200
        response_data = resp.json()

        # Verify the response structure matches DocumentLayoutBridge
        assert response_data["name"] == "test_layout"
        assert response_data["data_model"] == "test_model"
        assert response_data["summary"] == "Test layout summary"
        assert response_data["extraction_schema"] == {
            "type": "object",
            "properties": {"field1": {"type": "string"}},
        }
        assert response_data["extraction_config"] == {"mode": "strict"}
        assert response_data["system_prompt"] == "Custom system prompt"
        assert "created_at" in response_data
        assert "updated_at" in response_data

        # Verify the database query was called correctly
        mock_find.assert_called_once()
        call_args = mock_find.call_args
        assert call_args[0][1] == normalize_name("test_model")  # data_model_name
        assert call_args[0][2] == normalize_name("test_layout")  # layout_name

    def test_get_layout_not_found(self, client: TestClient):
        """Test layout not found scenario."""
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.get(
                "/api/v2/document-intelligence/layouts/nonexistent_layout",
                params={"data_model_name": "test_model"},
            )

        assert resp.status_code == 404
        error_data = resp.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.NOT_FOUND.value.code
        assert "nonexistent_layout" in error_data["error"]["message"]
        assert "test_model" in error_data["error"]["message"]

    def test_get_layout_missing_data_model_param(self, client: TestClient):
        """Test missing data_model_name query parameter."""
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/layouts/test_layout")

        # FastAPI should return 422 for missing required query parameter
        assert resp.status_code == 422
        error_data = resp.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code

    def test_get_layout_database_error(self, client: TestClient):
        """Test database error handling."""
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                side_effect=Exception("Database connection failed"),
            ),
        ):
            resp = client.get(
                "/api/v2/document-intelligence/layouts/test_layout",
                params={"data_model_name": "test_model"},
            )

        assert resp.status_code == 500
        error_data = resp.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.UNEXPECTED.value.code
        assert "Failed to get layout" in error_data["error"]["message"]


class TestUpdateLayout:
    """Tests for the update_layout (PUT) endpoint."""

    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                ),
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=5432,
                    kind=DataServerEndpointKind.MYSQL,
                ),
            ],
        )

    def test_update_layout_success(self, client: TestClient):
        """Test successful layout update."""
        payload = {
            "name": "invoice_v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object"},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Updated invoice layout",
            "extraction_config": {"threshold": 0.9},
            "prompt": "Updated prompt",
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
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            with patch.object(existing_layout, "update") as update:
                response = client.put(
                    "/api/v2/document-intelligence/layouts/invoice_v1?data_model_name=invoice",
                    json=payload,
                )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        find_by_name.assert_called_once_with(fake_ds, "invoice", "invoice_v1")
        update.assert_called_once_with(fake_ds)

        # Verify fields were updated (partial update behavior)
        assert existing_layout.extraction_schema == {"type": "object"}
        assert existing_layout.translation_schema == expected_wrapped
        assert existing_layout.summary == "Updated invoice layout"
        assert existing_layout.extraction_config == {"threshold": 0.9}
        assert existing_layout.system_prompt == "Updated prompt"

    def test_update_layout_not_found(self, client: TestClient):
        """Test updating a layout that doesn't exist."""
        payload = {
            "name": "nonexistent",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object"},
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
            ),
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.put(
                "/api/v2/document-intelligence/layouts/nonexistent?data_model_name=invoice",
                json=payload,
            )

        assert response.status_code == 404
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.NOT_FOUND.value.code
        assert "not found" in error_data["error"]["message"]

    def test_update_layout_partial_update(self, client: TestClient):
        """Test partial update functionality - only updates non-null fields."""
        payload = {
            "name": "invoice_v1",
            "data_model_name": "invoice",
            "summary": "Updated summary only",
            # Only updating summary, other fields should remain unchanged
        }

        storage_instance = StorageService.get_instance()
        existing_layout = Mock()
        existing_layout.extraction_schema = {"original": "schema"}
        existing_layout.translation_schema = {"original": "translation"}
        existing_layout.extraction_config = {"original": "config"}
        existing_layout.system_prompt = "Original prompt"

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
            ),
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            with patch.object(existing_layout, "update") as update:
                response = client.put(
                    "/api/v2/document-intelligence/layouts/invoice_v1?data_model_name=invoice",
                    json=payload,
                )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        # Only summary should be updated, others should remain original
        assert existing_layout.summary == "Updated summary only"
        assert existing_layout.extraction_schema == {"original": "schema"}  # unchanged
        assert existing_layout.translation_schema == {"original": "translation"}  # unchanged
        assert existing_layout.extraction_config == {"original": "config"}  # unchanged
        assert existing_layout.system_prompt == "Original prompt"  # unchanged
        update.assert_called_once_with(fake_ds)


class TestDeleteLayout:
    """Tests for the delete_layout endpoint."""

    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                ),
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=5432,
                    kind=DataServerEndpointKind.MYSQL,
                ),
            ],
        )

    def test_delete_layout_success(self, client: TestClient):
        """Test successful layout deletion."""
        storage_instance = StorageService.get_instance()
        mock_layout = Mock()
        mock_layout.delete.return_value = True

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
                return_value=mock_layout,
            ) as find_by_name,
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.delete(
                "/api/v2/document-intelligence/layouts/invoice_v1?data_model_name=invoice"
            )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        find_by_name.assert_called_once_with(fake_ds, "invoice", "invoice_v1")
        mock_layout.delete.assert_called_once_with(fake_ds)

    def test_delete_layout_not_found(self, client: TestClient):
        """Test deleting a layout that doesn't exist."""
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
            ),
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.delete(
                "/api/v2/document-intelligence/layouts/nonexistent?data_model_name=invoice"
            )

        assert response.status_code == 404
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.NOT_FOUND.value.code
        assert "not found" in error_data["error"]["message"]

    def test_delete_layout_delete_failed(self, client: TestClient):
        """Test when layout.delete() returns False."""
        storage_instance = StorageService.get_instance()
        mock_layout = Mock()
        mock_layout.delete.return_value = False

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
                return_value=mock_layout,
            ),
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.delete(
                "/api/v2/document-intelligence/layouts/invoice_v1?data_model_name=invoice"
            )

        assert response.status_code == 500
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.UNEXPECTED.value.code
        assert "Failed to delete layout" in error_data["error"]["message"]

    def test_delete_layout_missing_data_model_param(self, client: TestClient):
        """Test delete layout without required data_model_name parameter."""
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
        ):
            fake_service = Mock()
            fake_ds = Mock()
            fake_service.get_docint_datasource.return_value = fake_ds
            get_service.return_value = fake_service

            response = client.delete("/api/v2/document-intelligence/layouts/invoice_v1")

        assert response.status_code == 422
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code


class TestGenerateLayoutFromFile:
    """Tests for the generate_layout_from_file endpoint."""

    def _override_dependencies(self, app: FastAPI, fake_file_manager, fake_client) -> None:
        app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
        app.dependency_overrides[get_agent_server_client] = (
            lambda agent_id, request=None, thread_id=None: fake_client
        )

    def test_generate_layout_from_file_direct_upload(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        """Uploading a file directly should upload via file manager and return uploaded_file."""
        storage_instance = StorageService.get_instance()

        # Minimal valid DIDS details so DocInt datasource dependency resolves
        valid_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                ),
            ],
        )

        fake_thread = Mock()

        class Uploaded:
            def __init__(self, file_ref: str):
                self.file_ref = file_ref

        fake_uploaded = Uploaded("uploaded-ref-123")

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[fake_uploaded])

        fake_client = Mock()
        fake_client.generate_extraction_schema.return_value = {"fields": []}
        fake_client._file_to_images.return_value = [{"value": "img-bytes"}]
        fake_client.generate_document_layout_name.return_value = "Invoice Layout"
        fake_client.summarize_with_args.return_value = "Layout summary"
        fake_client.create_mapping.return_value = "[]"

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
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name="invoice", model_schema={"title": "Invoice"}),
            ) as mock_find_model,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.validate_schema",
                return_value={"fields": []},
            ),
        ):
            self._override_dependencies(fastapi_app, fake_file_manager, fake_client)

            response = client.post(
                "/api/v2/document-intelligence/layouts/generate",
                params={
                    "data_model_name": "Invoice",
                    "thread_id": "thread-1",
                    "agent_id": "agent-1",
                },
                files={
                    "file": (
                        "sample.pdf",
                        b"%PDF-1.4\n...",
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "layout" in body
        assert isinstance(body["layout"], dict)
        assert body["layout"].get("extraction_schema") == {"fields": []}
        assert "translation_schema" in body["layout"]
        assert body.get("file") is not None

        fake_file_manager.upload.assert_awaited()
        mock_find_model.assert_called_once()
        fake_client.generate_extraction_schema.assert_called_once()

        fake_client._file_to_images.assert_called_once()
        fake_client.generate_document_layout_name.assert_called_once()
        fake_client.summarize_with_args.assert_called_once()
        fake_client.create_mapping.assert_called_once()


class TestGenerateDataModelFromDocument:
    """Tests for the generate_layout_from_file endpoint."""

    def _override_dependencies(self, app: FastAPI, fake_file_manager, fake_client) -> None:
        app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
        app.dependency_overrides[get_agent_server_client] = (
            lambda agent_id, request=None, thread_id=None: fake_client
        )

    def test_generate_data_model_from_file_direct_upload(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        """Uploading a file directly should upload via file manager and return uploaded_file."""
        storage_instance = StorageService.get_instance()

        # Minimal valid DIDS details so DocInt datasource dependency resolves
        valid_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                )
            ],
        )

        fake_thread = Mock()

        class Uploaded:
            def __init__(self, file_ref: str):
                self.file_ref = file_ref

        fake_uploaded = Uploaded("uploaded-ref-123")

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[fake_uploaded])

        fake_client = Mock()
        fake_client.generate_schema_from_document.return_value = {"fields": []}

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
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)),
        ):
            self._override_dependencies(fastapi_app, fake_file_manager, fake_client)

            response = client.post(
                "/api/v2/document-intelligence/data-models/generate",
                params={
                    "thread_id": "thread-1",
                    "agent_id": "agent-1",
                },
                files={
                    "file": (
                        "sample.pdf",
                        b"%PDF-1.4\n...",
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "model_schema" in body
        assert "uploaded_file" in body

        fake_file_manager.upload.assert_awaited()
        fake_client.generate_schema_from_document.assert_called_once()

    def test_generate_data_model_from_file_with_file_ref(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        """Providing a file ref should resolve from storage and not return
        uploaded_file in response.
        """
        storage_instance = StorageService.get_instance()

        valid_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                )
            ],
        )

        fake_thread = Mock()

        class StoredFile:
            def __init__(self, file_ref: str):
                self.file_ref = file_ref

        original_stored = StoredFile("file-ref-xyz")
        refreshed_stored = StoredFile("file-ref-xyz-refreshed")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[refreshed_stored])

        fake_client = Mock()
        fake_client.generate_schema_from_document.return_value = {"fields": ["a", "b"]}

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
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=original_stored),
            ) as mock_get_file_by_ref,
        ):
            self._override_dependencies(fastapi_app, fake_file_manager, fake_client)

            response = client.post(
                "/api/v2/document-intelligence/data-models/generate",
                params={
                    "thread_id": "thread-2",
                    "agent_id": "agent-2",
                },
                data={"file": "file-ref-xyz"},
            )

        assert response.status_code == 200
        body = response.json()
        assert "model_schema" in body
        assert "uploaded_file" not in body

        mock_get_file_by_ref.assert_awaited()
        fake_file_manager.refresh_file_paths.assert_awaited()
        fake_client.generate_schema_from_document.assert_called_once()


@pytest.fixture
def parse_response() -> ParseResponse:
    return ParseResponse(
        duration=0,
        job_id="job-1",
        usage=ParseUsage(num_pages=1),
        result=ResultFullResult(
            chunks=[
                ResultFullResultChunk(
                    content="test",
                    embed="test",
                    blocks=[
                        ResultFullResultChunkBlock(
                            bbox=BoundingBox(left=0, page=0, top=0, width=0, height=0),
                            content="test",
                            type="Text",
                        )
                    ],
                )
            ],
            type="full",
        ),
    )


class TestParseDocumentEndpoints:
    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

    def test_parse_with_file_ref_success(self, client: TestClient, parse_response: ParseResponse):
        storage_instance = StorageService.get_instance()

        # Fakes
        thread = SimpleNamespace(id="thread-1")
        stored_file = SimpleNamespace(file_id="file-123")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored_file])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"file-bytes")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.return_value = "https://files.example.com/u/abc"
        fake_extraction_client.parse.return_value = parse_response

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                data={"file": "file-ref-xyz"},
            )

        assert resp.status_code == 200
        assert resp.json() == parse_response.result.model_dump(mode="json")

    def test_parse_with_upload_success(self, client: TestClient, parse_response: ParseResponse):
        storage_instance = StorageService.get_instance()

        # Fakes
        thread = SimpleNamespace(id="thread-1")
        uploaded = SimpleNamespace(file_id="new-file-999")

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[uploaded])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"payload")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.return_value = "https://files.example.com/u/def"
        fake_extraction_client.parse.return_value = parse_response

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                files={"file": ("test.txt", b"hello", "text/plain")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body == parse_response.result.model_dump(mode="json")

    def test_parse_thread_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        fake_file_manager = Mock()
        fake_extraction_client = Mock()

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=None)),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "missing"},
                data={"file": "file-ref"},
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "thread missing not found" in err["message"].lower()

    def test_parse_file_ref_not_found_in_storage(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="thread-1")
        fake_file_manager = Mock()
        fake_extraction_client = Mock()

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                data={"file": "unknown-file"},
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "file unknown-file not found (storage)" in err["message"].lower()

    def test_parse_file_ref_refresh_returns_empty(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="thread-1")
        stored_file = SimpleNamespace(file_id="file-123")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[])
        fake_extraction_client = Mock()

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                data={"file": "stale-file"},
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "file stale-file not found (refresh)" in err["message"].lower()

    @pytest.mark.parametrize(
        ("raised", "expected_code", "expected_message_substr"),
        [
            (
                UploadForbiddenError("http/403 - forbidden"),
                ErrorCode.UNAUTHORIZED,
                "couldn't connect",
            ),
            (UploadForbiddenError("API key invalid"), ErrorCode.UNAUTHORIZED, "couldn't connect"),
            (
                UploadMissingPresignedUrlError("No presigned URL returned"),
                ErrorCode.UNEXPECTED,
                "upload failed",
            ),
            (
                UploadMissingFileIdError("No file ID returned"),
                ErrorCode.UNEXPECTED,
                "upload failed",
            ),
        ],
    )
    def test_parse_upload_errors_map_to_platform_error(
        self,
        client: TestClient,
        raised: Exception,
        expected_code: ErrorCode,
        expected_message_substr: str,
    ):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="thread-1")
        uploaded = SimpleNamespace(file_id="fid-1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[uploaded])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"file-bytes")

        fake_extraction_client = Mock()
        # Raise during upload/parse block
        fake_extraction_client.upload.side_effect = raised

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=uploaded),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                data={"file": "file-ref-xyz"},
            )

        err = resp.json()["error"]
        assert err["code"] == expected_code.value.code
        assert expected_message_substr in err["message"].lower()


class TestDataQualityChecksEndpoints:
    """Tests for generate and execute data quality checks."""

    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP)
            ],
        )

    def _override_client_dependency(self, app: FastAPI, fake_client) -> None:
        app.dependency_overrides[get_agent_server_client] = (
            lambda agent_id, request=None, thread_id=None: fake_client
        )

    def test_generate_quality_checks_success(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_ds = Mock()

        sample_model = SimpleNamespace(
            description="Model description",
            views=[{"name": "v_items", "sql": "SELECT * FROM items"}],
        )

        class _FakeTable:
            def __init__(self):
                self.columns = ["document_id", "value"]
                self.rows = [["d1", 1], ["d2", 2]]

        class _FakeResult:
            def to_table(self):
                return _FakeTable()

        fake_ds.execute_sql.return_value = _FakeResult()

        fake_client = Mock()
        # New endpoint validates rules into ValidationRule, so use correct keys
        fake_rules = [
            {"rule_name": "rule1", "sql_query": "SELECT 1", "rule_description": "desc1"},
            {"rule_name": "rule2", "sql_query": "SELECT 2", "rule_description": "desc2"},
            {"rule_name": "rule3", "sql_query": "SELECT 3", "rule_description": "desc3"},
        ]
        fake_client.generate_validation_rules.return_value = fake_rules

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=sample_model,
            ) as mock_find_by_name,
        ):
            fake_service.get_docint_datasource.return_value = fake_ds
            self._override_client_dependency(fastapi_app, fake_client)

            resp = client.post(
                "/api/v2/document-intelligence/quality-checks/generate",
                params={"agent_id": "agent-1"},
                json={
                    "data_model_name": "Invoices",
                    "description": "Generate a few checks",
                    "limit": 2,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "quality_checks" in body
        assert isinstance(body["quality_checks"], list)
        assert len(body["quality_checks"]) == 2
        # Response items are serialized ValidationRule objects; compare by fields
        assert body["quality_checks"] == fake_rules[:2]
        mock_find_by_name.assert_called_once()
        fake_client.generate_validation_rules.assert_called_once()

    def test_generate_quality_checks_data_model_not_found(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        fake_client = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
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
            self._override_client_dependency(fastapi_app, fake_client)
            resp = client.post(
                "/api/v2/document-intelligence/quality-checks/generate",
                params={"agent_id": "agent-1"},
                json={
                    "data_model_name": "missing",
                    "description": "desc",
                    "limit": 1,
                },
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_generate_quality_checks_missing_views(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        fake_client = Mock()

        sample_model = SimpleNamespace(description="desc", views=None)

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=sample_model,
            ),
        ):
            self._override_client_dependency(fastapi_app, fake_client)
            resp = client.post(
                "/api/v2/document-intelligence/quality-checks/generate",
                params={"agent_id": "agent-1"},
                json={
                    "data_model_name": "Invoices",
                    "description": "checks",
                    "limit": 3,
                },
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "no views have been defined for the data model" in err["message"].lower()

    def test_execute_quality_checks_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_ds = Mock()
        fake_service.get_docint_datasource.return_value = fake_ds

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.validate_document_extraction",
                return_value={
                    "overall_status": "passed",
                    "results": [],
                    "passed": 1,
                    "failed": 0,
                    "errors": 0,
                },
            ) as mock_validate,
        ):
            resp = client.post(
                "/api/v2/document-intelligence/quality-checks/execute",
                json={
                    "document_id": "doc-123",
                    "quality_checks": [
                        {
                            "rule_name": "non_empty",
                            "sql_query": "SELECT * FROM v WHERE id IS NOT NULL",
                            "rule_description": "id must be present",
                        }
                    ],
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "overall_status": "passed",
            "results": [],
            "passed": 1,
            "failed": 0,
            "errors": 0,
        }
        mock_validate.assert_called_once()

    def test_execute_quality_checks_failed_validation_returns_200(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_ds = Mock()
        fake_service.get_docint_datasource.return_value = fake_ds

        failed_summary = {
            "overall_status": "failed",
            "results": [
                {
                    "rule_name": "non_empty",
                    "status": "failed",
                    "description": "Found 2 rows with NULL id",
                    "error_message": None,
                    "sql_query": "SELECT * FROM v WHERE id IS NOT NULL",
                    "context": None,
                }
            ],
            "passed": 0,
            "failed": 1,
            "errors": 0,
        }

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.validate_document_extraction",
                return_value=failed_summary,
            ) as mock_validate,
        ):
            resp = client.post(
                "/api/v2/document-intelligence/quality-checks/execute",
                json={
                    "document_id": "doc-123",
                    "quality_checks": [
                        {
                            "rule_name": "non_empty",
                            "sql_query": "SELECT * FROM v WHERE id IS NOT NULL",
                            "rule_description": "id must be present",
                        }
                    ],
                },
            )

        assert resp.status_code == 200
        assert resp.json() == failed_summary
        mock_validate.assert_called_once()


class TestExtractDocumentEndpoints:
    def _valid_details(self) -> DataServerDetails:
        return DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=47334,
                    kind=DataServerEndpointKind.HTTP,
                ),
                DataServerEndpoint(
                    host="127.0.0.1",
                    port=5432,
                    kind=DataServerEndpointKind.MYSQL,
                ),
            ],
        )

    def test_extract_with_layout_name_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        # Fakes
        thread = SimpleNamespace(id="thread-1")
        stored = SimpleNamespace(file_id="fid-1", file_ref="ref-1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"bytes")

        fake_extraction_client = Mock()
        fake_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_extraction_client.upload.return_value = "doc-1"
        fake_extraction_client.extract.return_value = SimpleNamespace(result=[{"ok": True}])

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Layout and model
        data_model_name = "Invoices"
        layout_name = "Standard V1"

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name=normalize_name(data_model_name), prompt="DM P"),
            ) as mock_find_model,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=SimpleNamespace(
                    extraction_schema={"type": "object"},
                    system_prompt="LAYOUT P",
                    extraction_config={"mode": "strict"},
                ),
            ) as mock_find_layout,
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto",
                        api_key=SecretString("k"),
                    )
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "thread-1",
                    "file_name": "file-xyz",
                    "data_model_name": data_model_name,
                    "layout_name": layout_name,
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Ensure lookups used normalized names
        mock_find_model.assert_called_once()
        mock_find_layout.assert_called_once()

        # Ensure extract called with merged prompt and schema/config
        fake_extraction_client.extract.assert_called_once()
        _, kwargs = fake_extraction_client.extract.call_args
        assert kwargs["schema"] == {"type": "object"}
        assert kwargs["extraction_config"] == {"mode": "strict"}
        assert kwargs["system_prompt"].startswith("BASE")
        assert "DM P" in kwargs["system_prompt"]
        assert "LAYOUT P" in kwargs["system_prompt"]

    def test_extract_with_document_layout_payload_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="t1")
        stored = SimpleNamespace(file_id="f1", file_ref="r1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"payload")

        fake_extraction_client = Mock()
        fake_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_extraction_client.upload.return_value = "doc-7"
        fake_extraction_client.extract.return_value = SimpleNamespace(result=[{"data": 1}])

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto",
                        api_key=SecretString("k"),
                    )
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "file-a",
                    "document_layout": {
                        "name": "Invoice L1",
                        "data_model_name": "Invoices",
                        "extraction_schema": {"type": "object"},
                        "prompt": "LP",
                        "extraction_config": {"k": "v"},
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"data": 1}
        fake_extraction_client.extract.assert_called_once()
        _, kwargs = fake_extraction_client.extract.call_args
        assert kwargs["schema"] == {"type": "object"}
        assert kwargs["extraction_config"] == {"k": "v"}
        assert kwargs["system_prompt"].startswith("BASE")
        assert "LP" in kwargs["system_prompt"]

    @pytest.mark.parametrize(
        ("payload", "expected_status"),
        [
            (
                {"file_name": "f", "layout_name": "l"},
                422,
            ),  # missing thread_id - FastAPI validation
            (
                {"thread_id": "t"},
                422,
            ),  # missing file_ref and layout/document - FastAPI validation
            (
                {"thread_id": "t", "file_name": "f"},
                400,
            ),  # missing layout/document - custom validation
            (
                {"thread_id": "t", "file_name": "f", "layout_name": "l"},
                400,
            ),  # missing dm name - custom validation
            (
                {
                    "thread_id": "t",
                    "file_name": "f",
                    "layout_name": "l",
                    "data_model_name": "dm",
                    "document_layout": {"name": "a", "data_model_name": "b"},
                },
                400,
            ),  # both provided - custom validation
        ],
    )
    def test_extract_validation_errors(
        self, client: TestClient, payload: dict, expected_status: int
    ):
        storage_instance = StorageService.get_instance()
        # Minimal service wiring so dependency resolves; validation should trigger before usage
        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        fake_integration = Mock()
        fake_integration.endpoint = "http://test.com"
        fake_api_key = Mock()
        fake_api_key.get_secret_value.return_value = "test-key"
        fake_integration.api_key = fake_api_key
        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(return_value=fake_integration),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json=payload,
            )

        assert resp.status_code == expected_status
        err = resp.json()["error"]

        # All validation errors use the custom ErrorResponse format with an error code
        if expected_status == 422:
            assert err["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code
        else:
            assert err["code"] == ErrorCode.BAD_REQUEST.value.code

    def test_extract_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        thread = SimpleNamespace(id="t1")

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=SimpleNamespace(file_id="f")),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "missing",
                    "layout_name": "l1",
                },
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_extract_layout_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        thread = SimpleNamespace(id="t1")

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=SimpleNamespace(file_id="f")),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "dm",
                    "layout_name": "l1",
                },
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_extract_layout_missing_schema(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        thread = SimpleNamespace(id="t1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(
            return_value=[SimpleNamespace(file_id="f")]
        )
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"x")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.return_value = "doc"

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=SimpleNamespace(file_id="f")),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=SimpleNamespace(
                    extraction_schema=None,
                    system_prompt=None,
                    extraction_config=None,
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto",
                        api_key=SecretString("k"),
                    )
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "dm",
                    "layout_name": "l1",
                },
            )

        assert resp.status_code == 500
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.UNEXPECTED.value.code
        assert "no extraction schema" in err["message"].lower()

    @pytest.mark.parametrize(
        ("raised", "expected_code", "expected_message_substr"),
        [
            (UploadForbiddenError("forbidden"), ErrorCode.UNAUTHORIZED, "couldn't connect"),
            (UploadMissingPresignedUrlError("no url"), ErrorCode.UNEXPECTED, "upload failed"),
            (UploadMissingFileIdError("no file id"), ErrorCode.UNEXPECTED, "upload failed"),
        ],
    )
    def test_extract_upload_errors_map(
        self,
        client: TestClient,
        raised: Exception,
        expected_code: ErrorCode,
        expected_message_substr: str,
    ):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="t1")
        stored = SimpleNamespace(file_id="f1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"b")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.side_effect = raised

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=SimpleNamespace(
                    extraction_schema={},
                    system_prompt=None,
                    extraction_config=None,
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "dm",
                    "layout_name": "l1",
                },
            )

        err = resp.json()["error"]
        assert err["code"] == expected_code.value.code
        assert expected_message_substr in err["message"].lower()

    @pytest.mark.parametrize(
        ("raised", "expected_code", "expected_message_substr"),
        [
            (
                ExtractFailedError("extract failed"),
                ErrorCode.UNPROCESSABLE_ENTITY,
                "document extraction failed",
            ),
            (Exception("network"), ErrorCode.UNEXPECTED, "something went wrong"),
        ],
    )
    def test_extract_job_errors_map(
        self,
        client: TestClient,
        raised: Exception,
        expected_code: ErrorCode,
        expected_message_substr: str,
    ):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="t1")
        stored = SimpleNamespace(file_id="f1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"b")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.return_value = "doc"
        fake_extraction_client.extract.side_effect = raised

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_dids_connection_details",
                new=AsyncMock(return_value=self._valid_details()),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DataModel.find_by_name",
                return_value=SimpleNamespace(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.DocumentLayout.find_by_name",
                return_value=SimpleNamespace(
                    extraction_schema={},
                    system_prompt=None,
                    extraction_config=None,
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "dm",
                    "layout_name": "l1",
                },
            )

        err = resp.json()["error"]
        assert err["code"] == expected_code.value.code
        assert expected_message_substr in err["message"].lower()

    @pytest.mark.parametrize(
        ("raised", "expected_code", "expected_message_substr"),
        [
            (
                ExtractFailedError("Extract job failed: segmentation error"),
                ErrorCode.UNPROCESSABLE_ENTITY,
                "document extraction failed",
            ),
            (
                Exception("Unknown job status: TIMEOUT"),
                ErrorCode.UNEXPECTED,
                "something went wrong while processing",
            ),
            (
                Exception("Network down"),
                ErrorCode.UNEXPECTED,
                "something went wrong while processing",
            ),
        ],
    )
    def test_parse_job_errors_map_to_platform_error(
        self,
        client: TestClient,
        raised: Exception,
        expected_code: ErrorCode,
        expected_message_substr: str,
    ):
        storage_instance = StorageService.get_instance()

        thread = SimpleNamespace(id="thread-1")
        uploaded = SimpleNamespace(file_id="fid-1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[uploaded])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"file-bytes")

        fake_extraction_client = Mock()
        fake_extraction_client.upload.return_value = "https://files.example.com/u/ghi"
        fake_extraction_client.parse.side_effect = raised

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=uploaded),
            ),
            patch.object(
                storage_instance,
                "get_document_intelligence_integration",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        endpoint="https://reducto", api_key=SecretString("k")
                    )
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.SyncExtractionClient",
                return_value=fake_extraction_client,
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse",
                params={"thread_id": "thread-1"},
                data={"file": "file-ref-xyz"},
            )

        err = resp.json()["error"]
        assert err["code"] == expected_code.value.code
        assert expected_message_substr in err["message"].lower()
