from datetime import datetime
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reducto.types import ExtractResponse, ParseResponse
from reducto.types.shared.bounding_box import BoundingBox
from reducto.types.shared.parse_response import (
    ResultFullResult,
    ResultFullResultChunk,
    ResultFullResultChunkBlock,
)
from reducto.types.shared.parse_response import ResultFullResult as ParseResult
from reducto.types.shared.parse_usage import ParseUsage
from sema4ai.data._data_source import ConnectionNotSetupError
from sema4ai_docint import DocumentLayout, normalize_name
from sema4ai_docint.extraction.reducto.async_ import Job, JobStatus, JobType
from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
)
from sema4ai_docint.models.constants import DATA_SOURCE_NAME

from agent_platform.core.data_connections import DataConnection, DataSources
from agent_platform.core.data_server.data_server import (
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.files import UploadedFile
from agent_platform.core.integrations import Integration
from agent_platform.core.payloads.data_connection import (
    DataConnectionTag,
    PostgresDataConnectionConfiguration,
)
from agent_platform.core.payloads.document_intelligence import (
    ExtractJobResult,
    ParseJobResult,
)
from agent_platform.core.payloads.upsert_document_layout import DocumentLayoutPayload
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import (
    get_agent_server_client,
    get_di_service,
    get_file_manager,
)
from agent_platform.server.api.private_v2.document_intelligence import document_intelligence
from agent_platform.server.api.private_v2.document_intelligence.document_intelligence import (
    DocumentIntelligenceConfigStatus,
)
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage.errors import (
    IntegrationNotFoundError,
)
from agent_platform.server.storage.option import StorageService


def create_mock_async_extraction_client_class(mock_client):
    """Create a mock AsyncExtractionClient class that returns the mock client."""

    class MockAsyncExtractionClient:
        """Mock for AsyncExtractionClient that supports async context manager protocol."""

        @classmethod
        def _new_async_reducto_client(cls, *args, **kwargs):
            """Mock the class method that the real constructor calls."""
            mock_client = AsyncMock()
            # Configure the mock to return a proper response object
            # The real code expects: upload_resp = await self._client.post(...) then
            # resp = upload_resp.json()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={"presigned_url": "https://example.com/upload"})
            mock_response.raise_for_status = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.close = AsyncMock()
            return mock_client

        def __init__(self, *args, **kwargs):
            # Mock the constructor behavior without calling the real implementation
            self._client = self._new_async_reducto_client()

        async def __aenter__(self):
            return mock_client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    return MockAsyncExtractionClient


async def create_mock_async_extraction_client_dependency(mock_client):
    """Create a mock async generator for the get_async_extraction_client dependency."""
    yield mock_client


def create_mock_integration_with_reducto_settings(api_key: str = "test-api-key") -> Integration:
    """Create a mock Integration object with ReductoSettings for testing."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings

    reducto_settings = ReductoSettings(
        endpoint="https://api.reducto.com", api_key=api_key, external_id="test-external-id"
    )

    return Integration(
        id="test-integration-id",
        kind=IntegrationKind.REDUCTO,
        settings=reducto_settings,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def create_mock_integration_with_data_server_settings(
    data_server_details: DataServerDetails,
) -> Integration:
    """Create a mock Integration object with DataServerSettings for testing."""
    from agent_platform.core.integrations.settings.data_server import (
        DataServerEndpoint,
        DataServerSettings,
    )

    # Convert DataServerDetails to DataServerSettings format
    endpoints = [
        DataServerEndpoint(
            host=ep.host,
            port=ep.port,
            kind=ep.kind.value if hasattr(ep.kind, "value") else str(ep.kind),
        )
        for ep in data_server_details.data_server_endpoints
    ]

    data_server_settings = DataServerSettings(
        username=data_server_details.username or "",
        password=data_server_details.password_str or "",
        endpoints=endpoints,
    )

    return Integration(
        id="test-data-server-integration-id",
        kind=IntegrationKind.DATA_SERVER,
        settings=data_server_settings,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def create_mock_get_integration_by_kind(
    data_server_details: DataServerDetails, reducto_api_key: str = "test-api-key"
):
    """Create a mock for get_integration_by_kind that returns appropriate Integration objects."""

    def mock_get_integration_by_kind(kind: str):
        if kind == IntegrationKind.DATA_SERVER:
            return create_mock_integration_with_data_server_settings(data_server_details)
        elif kind == IntegrationKind.REDUCTO:
            return create_mock_integration_with_reducto_settings(reducto_api_key)
        else:
            raise IntegrationNotFoundError(kind)

    return AsyncMock(side_effect=mock_get_integration_by_kind)


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
            == "Document Intelligence Data Server connection details not found"
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(valid_details),
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
        DataServerDetails(
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
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
        DataServerDetails(
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
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
        """POST /document-intelligence should persist integrations using v2_integration table."""
        payload = {
            "integrations": [
                {
                    "type": "reducto",
                    "endpoint": "https://reducto.example.com",
                    "api_key": "secret-key",
                    "external_id": "reducto-workspace-123",
                }
            ],
            "data_server": {
                "credentials": {"username": "user", "password": "pass"},
                "api": {
                    "http": {"url": "127.0.0.1", "port": 47334},
                    "mysql": {"host": "127.0.0.1", "port": 5432},
                },
            },
            "data_connection_id": "conn-1",
        }

        storage_instance = StorageService.get_instance()

        from agent_platform.core.integrations import Integration
        from agent_platform.core.integrations.settings.data_server import (
            DataServerEndpoint,
            DataServerSettings,
        )
        from agent_platform.core.integrations.settings.reducto import ReductoSettings

        mock_data_server_integration = Integration(
            id="test-id-1",
            kind=IntegrationKind.DATA_SERVER,
            settings=DataServerSettings(
                username="user",
                password="pass",
                endpoints=[
                    DataServerEndpoint(host="127.0.0.1", port=47334, kind="http"),
                    DataServerEndpoint(host="127.0.0.1", port=5432, kind="mysql"),
                ],
            ),
        )

        mock_reducto_integration = Integration(
            id="test-id-2",
            kind=IntegrationKind.REDUCTO,
            settings=ReductoSettings(
                endpoint="https://reducto.example.com",
                api_key="secret-key",
                external_id="reducto-workspace-123",
            ),
        )

        mock_integrations = [mock_data_server_integration, mock_reducto_integration]
        mock_data_connections = [
            MagicMock(id="conn-1", tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE]),
            MagicMock(id="conn-2", tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE]),
        ]

        # Create a mock data connection with proper UUID
        from agent_platform.core.data_connections.data_connections import DataConnection
        from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

        mock_data_connection = DataConnection(
            id="conn-1",
            name="test-connection",
            description="Test connection",
            engine="postgres",
            configuration=PostgresDataConnectionConfiguration(
                host="localhost",
                port=5432,
                database="testdb",
                user="testuser",
                password="testpass",
                schema="public",
                sslmode=None,
            ),
            external_id="test-external-id",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE],
        )

        with (
            patch.object(
                storage_instance,
                "upsert_integration",
                new=AsyncMock(),
            ) as upsert_integration,
            patch.object(
                storage_instance,
                "clear_data_connection_tag",
                new=AsyncMock(),
            ) as clear_data_connection_tag,
            patch.object(
                storage_instance,
                "add_data_connection_tag",
                new=AsyncMock(),
            ) as add_data_connection_tag,
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=mock_integrations),
            ),
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=mock_data_connections),
            ),
            patch.object(
                storage_instance,
                "get_data_connection",
                new=AsyncMock(return_value=mock_data_connection),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.DataSource.model_validate",
                return_value=Mock(),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_database",
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_data_source",
            ),
        ):
            response = client.post("/api/v2/document-intelligence", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

        assert upsert_integration.await_count == 2

        clear_data_connection_tag.assert_awaited_once_with(DataConnectionTag.DOCUMENT_INTELLIGENCE)

        assert add_data_connection_tag.await_count == 1
        add_data_connection_tag.assert_any_await("conn-1", DataConnectionTag.DOCUMENT_INTELLIGENCE)

    def test_upsert_document_intelligence_minimal_payload(self, client: TestClient):
        """POST /document-intelligence should work with minimal payload (only data_server)."""
        payload = {
            "data_server": {
                "credentials": {"username": "user", "password": "pass"},
                "api": {
                    "http": {"url": "127.0.0.1", "port": 47334},
                    "mysql": {"host": "127.0.0.1", "port": 5432},
                },
            },
            "data_connection_id": None,
        }

        storage_instance = StorageService.get_instance()

        from agent_platform.core.integrations import Integration
        from agent_platform.core.integrations.settings.data_server import (
            DataServerEndpoint,
            DataServerSettings,
        )

        mock_data_server_integration = Integration(
            id="test-id-1",
            kind=IntegrationKind.DATA_SERVER,
            settings=DataServerSettings(
                username="user",
                password="pass",
                endpoints=[
                    DataServerEndpoint(host="127.0.0.1", port=47334, kind="http"),
                    DataServerEndpoint(host="127.0.0.1", port=5432, kind="mysql"),
                ],
            ),
        )

        mock_integrations = [mock_data_server_integration]
        mock_data_connections = []

        with (
            patch.object(
                storage_instance,
                "upsert_integration",
                new=AsyncMock(),
            ) as upsert_integration,
            patch.object(
                storage_instance,
                "add_data_connection_tag",
                new=AsyncMock(),
            ) as add_data_connection_tag,
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=mock_integrations),
            ),
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=mock_data_connections),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.DataSource.model_validate",
                return_value=Mock(),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_database",
            ),
        ):
            response = client.post("/api/v2/document-intelligence", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

        assert upsert_integration.await_count == 1

        add_data_connection_tag.assert_not_awaited()

    def test_upsert_document_intelligence_accepts_single_data_connection_id(
        self, client: TestClient
    ):
        """POST /document-intelligence should accept single data_connection_id."""
        payload = {
            "data_server": {
                "credentials": {"username": "user", "password": "pass"},
                "api": {
                    "http": {"url": "127.0.0.1", "port": 47334},
                    "mysql": {"host": "127.0.0.1", "port": 5432},
                },
            },
            "data_connection_id": "conn-1",
        }

        storage_instance = StorageService.get_instance()

        from agent_platform.core.integrations import Integration
        from agent_platform.core.integrations.settings.data_server import (
            DataServerEndpoint,
            DataServerSettings,
        )

        mock_data_server_integration = Integration(
            id="test-id-1",
            kind=IntegrationKind.DATA_SERVER,
            settings=DataServerSettings(
                username="user",
                password="pass",
                endpoints=[
                    DataServerEndpoint(host="127.0.0.1", port=47334, kind="http"),
                    DataServerEndpoint(host="127.0.0.1", port=5432, kind="mysql"),
                ],
            ),
        )

        mock_integrations = [mock_data_server_integration]
        mock_data_connections = [
            MagicMock(id="conn-1", tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE]),
            MagicMock(id="conn-2", tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE]),
        ]

        # Create a mock data connection with proper UUID
        from agent_platform.core.data_connections.data_connections import DataConnection
        from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

        mock_data_connection = DataConnection(
            id="conn-1",
            name="test-connection",
            description="Test connection",
            engine="postgres",
            configuration=PostgresDataConnectionConfiguration(
                host="localhost",
                port=5432,
                database="testdb",
                user="testuser",
                password="testpass",
                schema="public",
                sslmode=None,
            ),
            external_id="test-external-id",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE],
        )

        with (
            patch.object(
                storage_instance,
                "upsert_integration",
                new=AsyncMock(),
            ),
            patch.object(
                storage_instance,
                "remove_data_connection_tag",
                new=AsyncMock(),
            ),
            patch.object(
                storage_instance,
                "add_data_connection_tag",
                new=AsyncMock(),
            ),
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=mock_integrations),
            ),
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=mock_data_connections),
            ),
            patch.object(
                storage_instance,
                "get_data_connection",
                new=AsyncMock(return_value=mock_data_connection),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.DataSource.model_validate",
                return_value=Mock(),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_database",
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_data_source",
            ),
        ):
            response = client.post("/api/v2/document-intelligence", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

    def test_upsert_document_intelligence_clears_existing_tags(self, client: TestClient):
        """POST /document-intelligence should clear existing data_intelligence tags."""
        payload = {
            "data_server": {
                "credentials": {"username": "user", "password": "pass"},
                "api": {
                    "http": {"url": "127.0.0.1", "port": 47334},
                    "mysql": {"host": "127.0.0.1", "port": 5432},
                },
            },
            "data_connection_id": "conn-1",
        }

        storage_instance = StorageService.get_instance()

        from agent_platform.core.integrations import Integration
        from agent_platform.core.integrations.settings.data_server import (
            DataServerEndpoint,
            DataServerSettings,
        )

        mock_data_server_integration = Integration(
            id="test-id-1",
            kind=IntegrationKind.DATA_SERVER,
            settings=DataServerSettings(
                username="user",
                password="pass",
                endpoints=[
                    DataServerEndpoint(host="127.0.0.1", port=47334, kind="http"),
                    DataServerEndpoint(host="127.0.0.1", port=5432, kind="mysql"),
                ],
            ),
        )

        mock_integrations = [mock_data_server_integration]
        mock_data_connections = []

        # Create a mock data connection with proper UUID
        from agent_platform.core.data_connections.data_connections import DataConnection
        from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

        mock_data_connection = DataConnection(
            id="conn-1",
            name="test-connection",
            description="Test connection",
            engine="postgres",
            configuration=PostgresDataConnectionConfiguration(
                host="localhost",
                port=5432,
                database="testdb",
                user="testuser",
                password="testpass",
                schema="public",
                sslmode=None,
            ),
            external_id="test-external-id",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE],
        )

        with (
            patch.object(
                storage_instance,
                "upsert_integration",
                new=AsyncMock(),
            ),
            patch.object(
                storage_instance,
                "clear_data_connection_tag",
                new=AsyncMock(),
            ) as clear_data_connection_tag,
            patch.object(
                storage_instance,
                "add_data_connection_tag",
                new=AsyncMock(),
            ) as add_data_connection_tag,
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=mock_integrations),
            ) as list_integrations,
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=mock_data_connections),
            ),
            patch.object(
                storage_instance,
                "get_data_connection",
                new=AsyncMock(return_value=mock_data_connection),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.DataSource.model_validate",
                return_value=Mock(),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_database",
                new=AsyncMock(),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_data_source",
            ),
        ):
            response = client.post("/api/v2/document-intelligence", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

        clear_data_connection_tag.assert_awaited_once_with(DataConnectionTag.DOCUMENT_INTELLIGENCE)

        add_data_connection_tag.assert_awaited_once_with(
            "conn-1", DataConnectionTag.DOCUMENT_INTELLIGENCE
        )

        assert list_integrations.await_count >= 1

    def test_get_document_intelligence_config_not_found(self, client: TestClient):
        """GET /document-intelligence should return 200 with not_configured status."""
        storage_instance = StorageService.get_instance()

        with patch.object(
            storage_instance,
            "list_integrations",
            new=AsyncMock(return_value=[]),
        ):
            response = client.get("/api/v2/document-intelligence")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == DocumentIntelligenceConfigStatus.NOT_CONFIGURED
        assert response_data["configuration"] is None
        assert response_data["error"] is not None
        assert response_data["error"]["code"] == ErrorCode.NOT_FOUND.value.code
        assert response_data["error"]["message"] == "Document Intelligence configuration not found"

    def test_get_document_intelligence_config_not_available(self, client: TestClient):
        """GET /document-intelligence should return 200 with not_available status on exception."""
        storage_instance = StorageService.get_instance()

        with patch.object(
            storage_instance,
            "list_integrations",
            new=AsyncMock(side_effect=Exception("Connection timeout")),
        ):
            response = client.get("/api/v2/document-intelligence")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == DocumentIntelligenceConfigStatus.NOT_AVAILABLE
        assert response_data["configuration"] is None
        assert response_data["error"] is not None
        assert response_data["error"]["code"] == ErrorCode.UNEXPECTED.value.code
        assert (
            response_data["error"]["message"] == "Document Intelligence DataServer is not available"
        )

    def test_get_document_intelligence_config_success(self, client: TestClient):
        """GET /document-intelligence should return the current configuration."""
        # Create test data
        data_server_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        data_connections = [
            DataConnection(
                id="conn-1",
                name="Test Connection",
                description="Test Connection Description",
                engine="postgres",
                configuration=PostgresDataConnectionConfiguration(
                    host="localhost",
                    port=5432,
                    database="test_db",
                    user="test_user",
                    password="test_password",
                ),
                external_id="conn-1",
                tags=[DataConnectionTag.DOCUMENT_INTELLIGENCE],
            )
        ]

        # Create mock integrations
        data_server_integration = create_mock_integration_with_data_server_settings(
            data_server_details
        )
        reducto_integration = create_mock_integration_with_reducto_settings("secret-key")
        all_integrations = [data_server_integration, reducto_integration]

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=all_integrations),
            ),
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=data_connections),
            ),
        ):
            response = client.get("/api/v2/document-intelligence")

        assert response.status_code == 200
        response_data = response.json()

        # Verify the response structure matches the new format
        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

        # Verify the configuration structure matches DocumentIntelligenceConfigPayload
        configuration = response_data["configuration"]
        assert "data_server" in configuration
        assert "integrations" in configuration
        assert "data_connections" in configuration

        # Verify data server details
        data_server = configuration["data_server"]
        assert data_server["credentials"]["username"] == "testuser"
        assert data_server["credentials"]["password"] == "testpass"
        assert data_server["api"]["http"]["url"] == "127.0.0.1"
        assert data_server["api"]["http"]["port"] == 47334
        assert data_server["api"]["mysql"]["host"] == "127.0.0.1"
        assert data_server["api"]["mysql"]["port"] == 5432

        # Verify integrations
        assert len(configuration["integrations"]) == 1
        integration = configuration["integrations"][0]
        assert integration["external_id"] == "test-external-id"
        assert integration["type"] == "reducto"
        assert integration["endpoint"] == "https://api.reducto.com"
        assert integration["api_key"] == "secret-key"

        # Verify data connection ID
        assert configuration["data_connection_id"] == "conn-1"

        # Verify data connections is empty (new format uses data_connection_id)
        assert len(configuration["data_connections"]) == 0

    def test_get_document_intelligence_config_empty_data(self, client: TestClient):
        """GET /document-intelligence should return empty lists when no integrations exist."""
        data_server_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        # Create mock integrations - only data server, no other integrations
        data_server_integration = create_mock_integration_with_data_server_settings(
            data_server_details
        )
        all_integrations = [data_server_integration]

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "list_integrations",
                new=AsyncMock(return_value=all_integrations),
            ),
            patch.object(
                storage_instance,
                "get_data_connections",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = client.get("/api/v2/document-intelligence")

        assert response.status_code == 200
        response_data = response.json()

        # Verify the response structure matches the new format
        assert response_data["status"] == DocumentIntelligenceConfigStatus.CONFIGURED
        assert response_data["error"] is None
        assert response_data["configuration"] is not None

        # Verify empty lists are returned
        configuration = response_data["configuration"]
        assert configuration["integrations"] == []
        assert configuration["data_connections"] == []

        # Verify data server details are still present
        assert configuration["data_server"]["credentials"]["username"] == "testuser"

    async def test_delete_di_when_not_configured(self, client: TestClient):
        """
        DELETE /document-intelligence should return ok even when no integrations exist
        """
        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "delete_integration",
                new=AsyncMock(),
            ) as delete_integration,
            patch.object(
                storage_instance,
                "clear_data_connection_tag",
                new=AsyncMock(),
            ) as clear_data_connection_tag,
        ):
            response = client.delete("/api/v2/document-intelligence")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        delete_integration.assert_awaited_once_with(IntegrationKind.REDUCTO)
        clear_data_connection_tag.assert_awaited_once_with(DataConnectionTag.DOCUMENT_INTELLIGENCE)

    async def test_delete_document_intelligence(self, client: TestClient):
        """
        DELETE /document-intelligence should clear all integrations and
        remove data_intelligence tags
        """
        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "delete_integration",
                new=AsyncMock(),
            ) as delete_integration,
            patch.object(
                storage_instance,
                "clear_data_connection_tag",
                new=AsyncMock(),
            ) as clear_data_connection_tag,
        ):
            response = client.delete("/api/v2/document-intelligence")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        assert delete_integration.await_count == 1
        delete_integration.assert_any_await(IntegrationKind.REDUCTO)

        clear_data_connection_tag.assert_awaited_once_with(DataConnectionTag.DOCUMENT_INTELLIGENCE)

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
            storage_instance,
            "get_integration_by_kind",
            new=AsyncMock(
                return_value=Mock(settings=Mock(model_dump=lambda: details.model_dump()))
            ),
        ):
            response = client.get("/api/v2/document-intelligence/ok")

        assert response.status_code == 412
        error = response.json()["error"]
        assert error["code"] == ErrorCode.PRECONDITION_FAILED.value.code
        assert expected_substring in error["message"]

    def test_get_all_layouts_returns_layouts(self, client: TestClient):
        """GET /document-intelligence/layouts should return layout summaries."""
        # Prepare valid connection details
        DataServerDetails(
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_all",
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
        DataServerDetails(
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_all",
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
                    id="docint-conn-1",
                    external_id="123",
                    name="docint-postgres",
                    description="Document Intelligence PostgreSQL Connection",
                    engine="postgres",
                    configuration=PostgresDataConnectionConfiguration(
                        user="testuser",
                        password="testpass",
                        host="localhost",
                        port=5432,
                        database="testdb",
                    ),
                ),
            },
        )

    @patch(
        "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_data_source"
    )
    @patch("agent_platform.server.data_server.data_source.DataSource")
    @patch(
        "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_database"
    )
    @patch(
        "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.DataSource"
    )
    async def test_build_datasource_success(
        self,
        mock_datasource,
        mock_initialize_database,
        mock_server_datasource,
        mock_initialize_data_source,
        sample_data_sources,
    ):
        """Test successful datasource creation and initialization."""
        # Setup DataSource mock instance returned by model_validate
        mock_docint_ds = Mock()
        mock_datasource.model_validate.return_value = mock_docint_ds

        # Setup server-side DataSource mock
        mock_admin_ds = Mock()
        mock_server_datasource.model_validate.return_value = mock_admin_ds

        # Call the function
        await document_intelligence._build_datasource(sample_data_sources)

        mock_initialize_data_source.assert_awaited_once_with(sample_data_sources)

        # Verify admin datasource was created with correct name
        assert mock_datasource.model_validate.call_count == 1
        mock_datasource.model_validate.assert_any_call(datasource_name="DocumentIntelligence")

        # Verify initialize_database was called
        mock_initialize_database.assert_called_once_with("postgres", mock_docint_ds)

    @patch(
        "agent_platform.server.api.private_v2.document_intelligence.document_intelligence.initialize_data_source"
    )
    @patch("agent_platform.server.data_server.data_source.DataSource")
    async def test_build_datasource_connection_error(
        self, mock_server_datasource, mock_initialize_data_source, sample_data_sources
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

    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )
        return create_mock_integration_with_data_server_settings(data_server_details)

    def _sample_data_model_payload(self) -> dict:
        return {
            "data_model": {
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
                "quality_checks": [
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
        self._valid_details()
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_all",
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

    def test_create_data_model_success(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Mock DI service dependency (same pattern as ingest tests)
        fake_di_service = Mock()
        fake_di_service.data_model.create_from_schema = Mock(return_value={"name": "invoices"})

        payload = self._sample_data_model_payload()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                side_effect=[None, SimpleNamespace(**self._sample_data_model_dict())],
            ) as mocked_find_by_name,
        ):
            # Override DI dependency
            fastapi_app.dependency_overrides[get_di_service] = lambda: fake_di_service
            resp = client.post(
                "/api/v2/document-intelligence/data-models",
                json=payload,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["data_model"]["name"] == "invoices"
        assert body["data_model"]["schema"]["type"] == "object"
        mocked_find_by_name.assert_called()
        fake_di_service.data_model.create_from_schema.assert_called_once()

    def test_create_data_model_failure_when_not_found_after_insert(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Mock DI service dependency
        fake_di_service = Mock()
        fake_di_service.data_model.create_from_schema = Mock(return_value={"name": "invoices"})

        payload = self._sample_data_model_payload()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            # This patch is to simulate the case of an internal error when the model is not
            # found right after creation.
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            fastapi_app.dependency_overrides[get_di_service] = lambda: fake_di_service
            resp = client.post("/api/v2/document-intelligence/data-models", json=payload)

        assert resp.status_code == 500
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.UNEXPECTED.value.code

    def test_get_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=SimpleNamespace(**self._sample_data_model_dict()),
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/data-models/invoices")

        assert resp.status_code == 200
        assert resp.json()["data_model"]["name"] == "invoices"

    def test_get_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/data-models/missing")

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_update_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code

    def test_update_data_model_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        payload = self._sample_data_model_payload()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=SimpleNamespace(**self._sample_data_model_dict(), update=Mock()),
            ) as mocked_find_by_name,
        ):
            resp = client.put("/api/v2/document-intelligence/data-models/invoices", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        # Ensure update was invoked on the returned instance
        instance = mocked_find_by_name.return_value
        instance.update.assert_called_once()

    def test_generate_description_success(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        # Arrange: thread and stored file
        thread = SimpleNamespace(id="t1")
        stored_file = SimpleNamespace(file_ref="file-ref-123")

        # Fake agent client that returns a description
        fake_agent_client = Mock()
        fake_agent_client.summarize = Mock(return_value="This is a generated description")

        with (
            patch.object(
                storage_instance,
                "get_thread",
                new=AsyncMock(return_value=thread),
            ),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
        ):
            # Override the agent client dependency
            fastapi_app.dependency_overrides[get_agent_server_client] = (
                lambda agent_id, request=None, thread_id=None: fake_agent_client
            )

            resp = client.post(
                "/api/v2/document-intelligence/data-models/generate-description",
                params={
                    "thread_id": "t1",
                    "file_ref": "file-ref-123",
                    "agent_id": "agent-1",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "This is a generated description"
        fake_agent_client.summarize.assert_called_once_with("file-ref-123")

    def test_generate_description_unexpected_error(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        # Arrange: thread and stored file
        thread = SimpleNamespace(id="t1")
        stored_file = SimpleNamespace(file_ref="bad-file-ref")

        # Fake agent client that raises a ValueError leading to 500
        fake_agent_client = Mock()
        fake_agent_client.summarize = Mock(side_effect=ValueError("boom"))

        with (
            patch.object(
                storage_instance,
                "get_thread",
                new=AsyncMock(return_value=thread),
            ),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
        ):
            # Override the agent client dependency
            fastapi_app.dependency_overrides[get_agent_server_client] = (
                lambda agent_id, request=None, thread_id=None: fake_agent_client
            )

            resp = client.post(
                "/api/v2/document-intelligence/data-models/generate-description",
                params={
                    "thread_id": "t1",
                    "file_ref": "bad-file-ref",
                    "agent_id": "agent-1",
                },
            )

        assert resp.status_code == 500
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.UNEXPECTED.value.code
        assert "Failed to generate data model description" in err["message"]

    def test_delete_data_model_not_found(self, client: TestClient):
        storage_instance = StorageService.get_instance()
        self._valid_details()
        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
        self._valid_details()
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

        payload = {"data_model": {"quality_checks": new_quality_checks}}

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
        self._valid_details()
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

        # Only provide quality_checks in the payload
        payload = {"data_model": {"quality_checks": inserted_quality_checks}}

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
        self._valid_details()
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=DummyDM(sample_model),
            ),
        ):
            resp = client.delete("/api/v2/document-intelligence/data-models/invoices")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestUpsertLayout:
    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_upsert_layout_inserts_when_not_exists(self, client: TestClient):
        payload = {
            "name": "invoice-v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object", "properties": {}},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
            "summary": "Invoice layout",
            "extraction_config": {"threshold": 0.8},
            "prompt": "You are a helpful layout model.",
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance"
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
                return_value=None,
            ) as find_by_name,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.insert"
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
            "extraction_schema": {"type": "object", "properties": {}},
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
                return_value=existing_layout,
            ) as find_by_name,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.insert",
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
        assert existing_layout.extraction_schema == {"type": "object", "properties": {}}
        assert existing_layout.translation_schema == expected_wrapped
        assert existing_layout.summary == "Invoice layout"
        assert existing_layout.extraction_config == {"threshold": 0.8}
        assert existing_layout.system_prompt == "You are a helpful layout model."

    def test_upsert_layout_normalizes_names_on_lookup(self, client: TestClient):
        payload = {
            "name": "Invoice Layout V1!!",
            "data_model_name": "Koch Invoices",
            "extraction_schema": {"type": "object", "properties": {}},
            "translation_schema": [{"mode": "rename", "source": "total", "target": "grand_total"}],
        }

        storage_instance = StorageService.get_instance()
        existing_layout = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
            "extraction_schema": {"type": "object", "properties": {}},
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
                return_value=None,
            ) as find_by_name,
        ):
            created_layout = None
            from sema4ai_docint.models import DocumentLayout

            original_insert = DocumentLayout.insert

            def mock_insert(self, ds):
                nonlocal created_layout
                created_layout = self

            try:
                DocumentLayout.insert = mock_insert

                fake_service = Mock()
                fake_ds = Mock()
                fake_service.get_docint_datasource.return_value = fake_ds
                get_service.return_value = fake_service

                response = client.post("/api/v2/document-intelligence/layouts", json=payload)

                assert response.status_code == 200
                assert response.json() == {"ok": True}
                find_by_name.assert_called_once()

                # Verify the created layout has normalized names
                assert created_layout is not None
                assert created_layout.name == normalize_name(payload["name"])  # type: ignore[index]
                assert created_layout.data_model == normalize_name(payload["data_model_name"])  # type: ignore[index]
            finally:
                # Restore the original insert method
                DocumentLayout.insert = original_insert

    def test_upsert_layout_reraises_platform_http_error(self, client: TestClient):
        """Test that PlatformHTTPError from underlying components is reraised without
        modification."""
        payload = {
            "name": "invoice-v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object", "properties": {}},
        }

        # Create a specific PlatformHTTPError to test with
        platform_error = PlatformHTTPError(ErrorCode.BAD_REQUEST, "Invalid schema format")

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance"
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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

    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
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
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_get_layout_success(self, client: TestClient):
        """Test successful layout retrieval."""
        storage_instance = StorageService.get_instance()

        # Mock data that represents a DocumentLayout from the database
        mock_document_layout = DocumentLayout(
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
                return_value=mock_document_layout,
            ) as mock_find,
        ):
            resp = client.get(
                "/api/v2/document-intelligence/layouts/test_layout",
                params={"data_model_name": "test_model"},
            )

        assert resp.status_code == 200
        actual_layout = DocumentLayoutPayload.model_validate(resp.json())

        # Verify the response structure matches DocumentLayoutPayload
        assert actual_layout.name == "test_layout"
        assert actual_layout.data_model_name == "test_model"
        assert actual_layout.summary == "Test layout summary"
        assert actual_layout.extraction_schema is not None
        assert actual_layout.extraction_schema.model_dump(mode="json", exclude_none=True) == {
            "type": "object",
            "properties": {"field1": {"type": "string"}},
        }
        assert actual_layout.extraction_config == {"mode": "strict"}
        assert actual_layout.prompt == "Custom system prompt"
        assert actual_layout.created_at
        assert actual_layout.updated_at

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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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

    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
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
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_update_layout_success(self, client: TestClient):
        """Test successful layout update."""
        payload = {
            "name": "invoice_v1",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object", "properties": {}},
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
        assert existing_layout.extraction_schema == {"type": "object", "properties": {}}
        assert existing_layout.translation_schema == expected_wrapped
        assert existing_layout.summary == "Updated invoice layout"
        assert existing_layout.extraction_config == {"threshold": 0.9}
        assert existing_layout.system_prompt == "Updated prompt"

    def test_update_layout_not_found(self, client: TestClient):
        """Test updating a layout that doesn't exist."""
        payload = {
            "name": "nonexistent",
            "data_model_name": "invoice",
            "extraction_schema": {"type": "object", "properties": {}},
        }

        storage_instance = StorageService.get_instance()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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

    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
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
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_delete_layout_success(self, client: TestClient):
        """Test successful layout deletion."""
        storage_instance = StorageService.get_instance()
        mock_layout = Mock()
        mock_layout.delete.return_value = True

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
            ) as get_service,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.layouts.DocumentLayout.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
        DataServerDetails(
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

        # Create a proper UploadedFile instance for testing
        fake_uploaded = UploadedFile(
            file_id="test-file-id",
            file_path="/tmp/sample.pdf",
            file_ref="uploaded-ref-123",
            file_hash="test-hash",
            file_size_raw=1024,
            mime_type="application/pdf",
            created_at=datetime.now(),
            embedded=False,
        )

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[fake_uploaded])

        fake_client = Mock()
        fake_client.generate_schema.return_value = {"type": "object", "properties": {}}
        fake_client._file_to_images.return_value = [{"value": "img-bytes"}]
        fake_client.generate_document_layout_name.return_value = "Invoice Layout"
        fake_client.summarize_with_args.return_value = "Layout summary"
        fake_client.create_mapping.return_value = "[]"

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=SimpleNamespace(name="invoice", model_schema={"title": "Invoice"}),
            ) as mock_find_model,
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
        assert body["layout"].get("extraction_schema") == {
            "type": "object",
            "properties": {},
            "required": None,
        }
        assert "translation_schema" in body["layout"]
        assert body.get("file") is not None

        fake_file_manager.upload.assert_awaited()
        mock_find_model.assert_called_once()
        fake_client.generate_schema.assert_called_once()

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
        DataServerDetails(
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

        fake_uploaded = UploadedFile(
            file_id="file-123",
            file_path="/path/to/file.pdf",
            file_ref="uploaded-ref-123",
            file_hash="hash123",
            file_size_raw=1024,
            mime_type="application/pdf",
            created_at=datetime.now(),
        )

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[fake_uploaded])

        fake_client = Mock()
        fake_client.generate_schema.return_value = {"fields": []}

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
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
        fake_client.generate_schema.assert_called_once()

    def test_generate_data_model_from_file_with_file_ref(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        """Providing a file ref should resolve from storage and not return
        uploaded_file in response.
        """
        storage_instance = StorageService.get_instance()

        DataServerDetails(
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
        fake_client.generate_schema.return_value = {"fields": ["a", "b"]}

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
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
        fake_client.generate_schema.assert_called_once()


class TestGenerateExtractionSchemaFromDocument:
    """Tests for the generate_schema endpoint."""

    def _override_dependencies(self, app: FastAPI, fake_file_manager, fake_client) -> None:
        app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
        app.dependency_overrides[get_agent_server_client] = (
            lambda agent_id, request=None, thread_id=None: fake_client
        )

    def test_generate_schema_direct_upload(self, client: TestClient, fastapi_app: FastAPI):
        """Uploading a file directly should upload via file manager and return uploaded_file."""
        storage_instance = StorageService.get_instance()

        fake_thread = Mock()

        fake_uploaded = UploadedFile(
            file_id="file-123",
            file_path="/path/to/file.pdf",
            file_ref="uploaded-ref-123",
            file_hash="hash123",
            file_size_raw=1024,
            mime_type="application/pdf",
            created_at=datetime.now(),
        )

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[fake_uploaded])

        fake_client = Mock()
        fake_client.generate_schema = Mock(return_value={"type": "object", "properties": {}})

        with patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)):
            self._override_dependencies(fastapi_app, fake_file_manager, fake_client)

            response = client.post(
                "/api/v2/document-intelligence/documents/generate-schema",
                params={
                    "thread_id": "thread-1",
                    "agent_id": "agent-123",
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
        assert "schema" in body
        assert "file" in body
        assert body["schema"] == {"type": "object", "properties": {}}
        assert body["file"]["file_ref"] == "uploaded-ref-123"

        fake_file_manager.upload.assert_awaited()
        fake_client.generate_schema.assert_called_once()

    def test_generate_schema_with_file_ref(self, client: TestClient, fastapi_app: FastAPI):
        """Providing a file ref should resolve from storage and not return uploaded_file."""
        storage_instance = StorageService.get_instance()

        fake_thread = Mock()

        class StoredFile:
            def __init__(self, file_ref: str):
                self.file_ref = file_ref

        original_stored = StoredFile("file-ref-xyz")
        refreshed_stored = StoredFile("file-ref-xyz-refreshed")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[refreshed_stored])

        fake_client = Mock()
        fake_client.generate_schema = Mock(
            return_value={"type": "object", "properties": {"field": {"type": "string"}}}
        )

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=fake_thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=original_stored),
            ) as mock_get_file_by_ref,
        ):
            self._override_dependencies(fastapi_app, fake_file_manager, fake_client)

            response = client.post(
                "/api/v2/document-intelligence/documents/generate-schema",
                params={
                    "thread_id": "thread-2",
                    "agent_id": "agent-456",
                },
                data={"file": "file-ref-xyz"},
            )

        assert response.status_code == 200
        body = response.json()
        assert "schema" in body
        assert body["file"] is None  # When using file ref, no new file is created
        assert body["schema"] == {"type": "object", "properties": {"field": {"type": "string"}}}

        mock_get_file_by_ref.assert_awaited()
        fake_file_manager.refresh_file_paths.assert_awaited()
        fake_client.generate_schema.assert_called_once()


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
    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_parse_with_file_ref_success(self, client: TestClient, parse_response: ParseResponse):
        storage_instance = StorageService.get_instance()

        # Fakes
        thread = SimpleNamespace(id="thread-1")
        stored_file = SimpleNamespace(file_id="file-123")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored_file])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"file-bytes")

        # Create a mock Job that will be returned by start_parse
        mock_job = Mock()
        mock_job.job_id = "parse-job-123"
        mock_job.job_type = JobType.PARSE
        mock_job.result = AsyncMock(return_value=parse_response)

        fake_extraction_client = Mock()
        fake_extraction_client.upload = AsyncMock(return_value="https://files.example.com/u/abc")
        fake_extraction_client.start_parse = AsyncMock(return_value=mock_job)

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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

        # Create a mock Job that will be returned by start_parse
        mock_job = Mock()
        mock_job.job_id = "parse-job-456"
        mock_job.job_type = JobType.PARSE
        mock_job.result = AsyncMock(return_value=parse_response)

        fake_extraction_client = Mock()
        fake_extraction_client.upload = AsyncMock(return_value="https://files.example.com/u/def")
        fake_extraction_client.start_parse = AsyncMock(return_value=mock_job)

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=None)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored_file),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
        fake_extraction_client.upload = AsyncMock(side_effect=raised)

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=uploaded),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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

    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP)
            ],
        )
        return create_mock_integration_with_data_server_settings(data_server_details)

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
        fake_rules = [
            {"rule_name": "rule1", "sql_query": "SELECT 1", "rule_description": "desc1"},
            {"rule_name": "rule2", "sql_query": "SELECT 2", "rule_description": "desc2"},
            {"rule_name": "rule3", "sql_query": "SELECT 3", "rule_description": "desc3"},
        ]

        def _gen_rules(*args, **kwargs):
            limit = kwargs.get("limit_count", 1)
            return fake_rules[:limit]

        fake_client.generate_validation_rules.side_effect = _gen_rules

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
                return_value=sample_model,
            ) as mock_find_by_name,
        ):
            fake_service.get_docint_datasource.return_value = fake_ds
            self._override_client_dependency(fastapi_app, fake_client)

            resp_with_limit = client.post(
                "/api/v2/document-intelligence/quality-checks/generate",
                params={"agent_id": "agent-1"},
                json={
                    "data_model_name": "Invoices",
                    "limit": 2,
                },
            )
            assert resp_with_limit.status_code == 200
            body = resp_with_limit.json()
            assert "quality_checks" in body
            assert isinstance(body["quality_checks"], list)
            assert len(body["quality_checks"]) == 2
            # Response items are serialized ValidationRule objects; compare by fields
            assert body["quality_checks"] == fake_rules[:2]
            fake_client.generate_validation_rules.assert_called_once()

            # Reset before issuing the second request
            fake_client.generate_validation_rules.reset_mock()

            # Second request
            resp_with_description = client.post(
                "/api/v2/document-intelligence/quality-checks/generate",
                params={"agent_id": "agent-1"},
                json={
                    "data_model_name": "Invoices",
                    "description": "Generate a check for a specific use-case",
                    "limit": 1,
                },
            )

            assert resp_with_description.status_code == 200
            body = resp_with_description.json()
        assert "quality_checks" in body
        assert isinstance(body["quality_checks"], list)
        assert len(body["quality_checks"]) == 1
        assert body["quality_checks"] == fake_rules[:1]
        fake_client.generate_validation_rules.assert_called_once()

        assert mock_find_by_name.call_count == 2

    def test_generate_quality_checks_bad_request(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        fake_client = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
        ):
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

        assert resp.status_code == 400
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.BAD_REQUEST.value.code
        assert "If a description is provided, limit count must be 1" in err["message"]

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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
                    "limit": 1,
                },
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "no views have been defined for the data model" in err["message"].lower()

    def test_generate_quality_checks_missing_views_empty_list(
        self, client: TestClient, fastapi_app: FastAPI
    ):
        storage_instance = StorageService.get_instance()

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()
        fake_client = Mock()

        sample_model = SimpleNamespace(description="desc", views=[])

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.data_models.DataModel.find_by_name",
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
                    "limit": 1,
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.quality_checks.validate_document_extraction",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.quality_checks.validate_document_extraction",
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


class TestAsyncDocumentEndpoints:
    """Tests for async document intelligence endpoints."""

    def test_parse_async_returns_job_immediately(self, client: TestClient):
        """Test that parse/async returns job_id and job_type immediately without waiting."""
        storage_instance = StorageService.get_instance()

        # Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="thread-1")
        uploaded = UploadedFile(
            file_id="new-file-123",
            file_path="/test/path",
            file_ref="ref-123",
            file_hash="test-hash",
            file_size_raw=1024,
            mime_type="application/pdf",
            created_at=datetime.now(),
        )

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[uploaded])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"test-content")

        # Create a proper Job instance (not just a Mock)
        mock_job = Job(job_id="parse-job-456", job_type=JobType.PARSE, client=Mock())

        fake_async_extraction_client = Mock()
        fake_async_extraction_client.upload = AsyncMock(return_value="doc-url-789")
        fake_async_extraction_client.start_parse = AsyncMock(return_value=mock_job)

        # Mock the integration as a dict instead of SimpleNamespace
        mock_integration = Mock()
        mock_integration.endpoint = "https://reducto"
        mock_integration.api_key = SecretString("key")

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse/async",
                params={"thread_id": "thread-1"},
                files={"file": ("test.pdf", b"pdf-content", "application/pdf")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "parse-job-456"
        assert body["job_type"] == JobType.PARSE
        assert "uploaded_file" in body
        assert body["uploaded_file"]["file_id"] == "new-file-123"

        # Verify async methods were called
        fake_async_extraction_client.upload.assert_awaited_once()
        fake_async_extraction_client.start_parse.assert_awaited_once()

    def test_extract_async_with_layout_returns_job(self, client: TestClient):
        """Test that extract/async with layout returns job_id and job_type immediately."""
        storage_instance = StorageService.get_instance()

        # Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="t1")
        stored = Mock(file_id="f1", file_ref="r1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"doc-bytes")

        # Create a proper Job instance (not just a Mock)
        mock_job = Job(job_id="extract-job-789", job_type=JobType.EXTRACT, client=Mock())

        fake_async_extraction_client = Mock()
        fake_async_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_async_extraction_client.upload = AsyncMock(return_value="doc-id-123")
        fake_async_extraction_client.start_extract = AsyncMock(return_value=mock_job)

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        DataServerDetails(
            username="user",
            password=SecretString("pass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name="invoice_model", prompt="Model prompt"),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=Mock(
                    extraction_schema={"type": "object"},
                    system_prompt="Layout prompt",
                    extraction_config={"mode": "fast"},
                ),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract/async",
                json={
                    "thread_id": "t1",
                    "file_name": "r1",
                    "data_model_name": "invoice_model",
                    "layout_name": "invoice_layout",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "extract-job-789"
        assert body["job_type"] == JobType.EXTRACT
        assert body["uploaded_file"] is None  # No new upload for existing file

        fake_async_extraction_client.start_extract.assert_awaited_once()

    def test_get_job_status_pending(self, client: TestClient):
        """Test getting status of a pending job."""
        fake_async_extraction_client = Mock()
        fake_async_extraction_client.get_job_status = AsyncMock(return_value="Pending")

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
        ):
            resp = client.get(
                "/api/v2/document-intelligence/jobs/test-job-123/status",
                params={"job_type": "parse"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"job_id": "test-job-123", "status": "Pending", "result_url": None}
        # The actual implementation uses Job.status() which calls client.get_job_status
        # But since we're creating a real Job object, we need to mock the right thing

    def test_get_job_result_parse_type(self, client: TestClient):
        """Test getting result of a completed parse job."""
        # Create a mock ParseResponse object
        mock_parse_response = Mock(spec=ParseResponse)
        mock_parse_result = Mock(spec=ParseResult)
        mock_parse_result.pages = [{"content": "parsed text"}]  # This is what the test expects
        mock_parse_response.result = mock_parse_result

        # Mock the extraction client Job.result() method returning the ParseResponse
        fake_async_extraction_client = Mock()
        # The job.result() method should return the ParseResponse, not wait_for_job

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
            # Mock the Job class and its result method
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.jobs.Job"
            ) as mock_job_class,
            # Mock the _create_job_result function to return what we expect
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.jobs._create_job_result"
            ) as mock_create_job_result,
        ):
            # Configure the Job mock to return our mocked response
            mock_job_instance = Mock()
            mock_job_instance.result = AsyncMock(return_value=mock_parse_response)
            # Mock status to return COMPLETED so get_job_result doesn't return 404

            mock_job_instance.status = AsyncMock(return_value=JobStatus.COMPLETED)
            mock_job_class.return_value = mock_job_instance

            # Configure _create_job_result to return the expected ParseJobResult

            expected_parse_result = {"pages": [{"content": "parsed text"}]}
            mock_create_job_result.return_value = ParseJobResult(result=expected_parse_result)  # type: ignore

            resp = client.get(
                "/api/v2/document-intelligence/jobs/parse-job-456/result",
                params={"job_type": "parse"},
            )

        assert resp.status_code == 200
        # The endpoint returns the ParseJobResult with both result and job_type
        expected_response = {"result": expected_parse_result, "job_type": "parse"}
        assert resp.json() == expected_response

    def test_get_job_result_extract_type(self, client: TestClient):
        """Test getting result of a completed extract job."""
        # Mock extract result
        mock_extract_result = {"extracted_data": {"invoice_id": "INV-123"}}
        mock_extract_citations = {
            "citations": {
                "invoice_id": {"bbox": {"left": 0.1, "top": 0.2, "width": 0.3, "height": 0.4}}
            }
        }

        # Create a mock ExtractResponse object
        mock_extract_response = Mock(spec=ExtractResponse)
        mock_extract_response.result = [mock_extract_result]
        mock_extract_response.citations = [mock_extract_citations]

        # Mock the extraction client (needed for dependency injection)
        fake_async_extraction_client = Mock()

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
            # Mock the Job class and its result method
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.jobs.Job"
            ) as mock_job_class,
            # Mock the _create_job_result function to return what we expect
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.jobs._create_job_result"
            ) as mock_create_job_result,
        ):
            # Configure the Job mock to return our mocked ExtractResponse
            mock_job_instance = Mock()
            mock_job_instance.result = AsyncMock(return_value=mock_extract_response)
            # Mock status to return COMPLETED so get_job_result doesn't return 404

            mock_job_instance.status = AsyncMock(return_value=JobStatus.COMPLETED)
            mock_job_class.return_value = mock_job_instance

            # Configure _create_job_result to return the expected ExtractJobResult

            mock_create_job_result.return_value = ExtractJobResult(
                result=mock_extract_result, citations=mock_extract_citations
            )

            resp = client.get(
                "/api/v2/document-intelligence/jobs/extract-job-789/result",
                params={"job_type": "extract"},
            )

        assert resp.status_code == 200
        # The endpoint returns the ExtractJobResult with both result and job_type
        expected_response = {
            "result": mock_extract_result,
            "citations": mock_extract_citations,
            "job_type": "extract",
        }
        assert resp.json() == expected_response

    def test_get_job_result_missing_job_type(self, client: TestClient):
        """Test that job_type query parameter is required."""
        with patch.object(
            StorageService.get_instance(),
            "get_integration_by_kind",
            new=create_mock_get_integration_by_kind(
                DataServerDetails(
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
                ),
                "test-api-key",
            ),
        ):
            resp = client.get("/api/v2/document-intelligence/jobs/job-123/result")

        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code

    def test_get_job_result_invalid_job_type(self, client: TestClient):
        """Test that invalid job_type is rejected."""
        with patch.object(
            StorageService.get_instance(),
            "get_integration_by_kind",
            new=create_mock_get_integration_by_kind(
                DataServerDetails(
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
                ),
                "test-api-key",
            ),
        ):
            resp = client.get(
                "/api/v2/document-intelligence/jobs/job-123/result",
                params={"job_type": "invalid_type"},
            )

        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code

    def test_get_job_result_job_failed(self, client: TestClient):
        """Test getting result when job failed."""
        # Mock the extraction client
        fake_async_extraction_client = Mock()

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
            # Mock the Job class to return FAILED status
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.jobs.Job"
            ) as mock_job_class,
        ):
            # Configure the Job mock to return FAILED status
            mock_job_instance = Mock()

            mock_job_instance.status = AsyncMock(return_value=JobStatus.FAILED)
            mock_job_class.return_value = mock_job_instance

            resp = client.get(
                "/api/v2/document-intelligence/jobs/job-123/result",
                params={"job_type": "parse"},
            )

        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == ErrorCode.UNPROCESSABLE_ENTITY.value.code
        assert "failed" in error["message"].lower()

    def test_parse_async_with_file_ref(self, client: TestClient):
        """Test async parse with existing file reference."""
        storage_instance = StorageService.get_instance()

        # Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="thread-1")
        stored = Mock(file_id="existing-file-456", file_ref="ref-456")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"existing-content")

        # Create a proper Job instance (not just a Mock)
        mock_job = Job(job_id="parse-job-789", job_type=JobType.PARSE, client=Mock())

        fake_async_extraction_client = Mock()
        fake_async_extraction_client.upload = AsyncMock(return_value="doc-url-999")
        fake_async_extraction_client.start_parse = AsyncMock(return_value=mock_job)

        with (
            patch.object(
                StorageService.get_instance(),
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_async_extraction_client),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/parse/async",
                params={"thread_id": "thread-1"},
                data={"file": "ref-456"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "parse-job-789"
        assert body["job_type"] == JobType.PARSE
        assert body["uploaded_file"] is None  # No new file uploaded

        fake_file_manager.refresh_file_paths.assert_awaited_once()
        fake_async_extraction_client.start_parse.assert_awaited_once()


class TestExtractDocumentEndpoints:
    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
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
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_extract_with_layout_name_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        # Fakes - Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="thread-1")
        stored = Mock(file_id="fid-1", file_ref="ref-1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"bytes")

        # Create a mock Job instance for start_extract return
        mock_job = Mock()
        mock_job.job_id = "extract-job-123"
        mock_job.job_type = JobType.EXTRACT

        # Create a mock ExtractResponse object that job.result() will return
        mock_extract_response = Mock(spec=ExtractResponse)
        mock_extract_response.result = [{"extracted": "data"}]
        mock_extract_response.citations = []
        # Mock job.result() to return the extract response (this is what extract endpoint calls now)
        mock_job.result = AsyncMock(return_value=mock_extract_response)

        fake_extraction_client = Mock()
        fake_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_extraction_client.upload = AsyncMock(return_value="doc-1")
        fake_extraction_client.extract = AsyncMock(return_value=Mock(result=[{"ok": True}]))
        fake_extraction_client.start_extract = AsyncMock(return_value=mock_job)
        fake_extraction_client.wait_for_job = AsyncMock(return_value=mock_extract_response)

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        # Layout and model
        data_model_name = "Invoices"
        layout_name = "Standard V1"

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name=normalize_name(data_model_name), prompt="DM P"),
            ) as mock_find_model,
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=Mock(
                    extraction_schema={"type": "object", "properties": {}},
                    system_prompt="LAYOUT P",
                    extraction_config={"mode": "strict"},
                ),
            ) as mock_find_layout,
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
        assert resp.json() == {
            "result": {"extracted": "data"},
            "citations": None,
        }

        # Ensure lookups used normalized names
        mock_find_model.assert_called_once()
        mock_find_layout.assert_called_once()

        # Ensure start_extract called with merged prompt and schema/config
        fake_extraction_client.start_extract.assert_called_once()
        _, kwargs = fake_extraction_client.start_extract.call_args
        assert kwargs["schema"] == {"type": "object", "properties": {}}
        assert kwargs["extraction_config"] == {"mode": "strict", "generate_citations": True}
        assert kwargs["system_prompt"].startswith("BASE")
        assert "DM P" in kwargs["system_prompt"]
        assert "LAYOUT P" in kwargs["system_prompt"]

    def test_extract_with_document_layout_payload_success(self, client: TestClient):
        storage_instance = StorageService.get_instance()

        # Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="t1")
        stored = Mock(file_id="f1", file_ref="r1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"payload")

        # Create a mock Job instance for start_extract return
        mock_job = Mock()
        mock_job.job_id = "extract-job-456"
        mock_job.job_type = JobType.EXTRACT

        # Create a mock ExtractResponse object that job.result() will return
        mock_extract_response = Mock(spec=ExtractResponse)
        mock_extract_response.result = [{"data": 1}]
        mock_extract_response.citations = []
        # Mock job.result() to return the extract response (this is what extract endpoint calls now)
        mock_job.result = AsyncMock(return_value=mock_extract_response)

        fake_extraction_client = Mock()
        fake_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_extraction_client.upload = AsyncMock(return_value="doc-7")
        fake_extraction_client.extract = AsyncMock(return_value=Mock(result=[{"data": 1}]))
        fake_extraction_client.start_extract = AsyncMock(return_value=mock_job)
        fake_extraction_client.wait_for_job = AsyncMock(return_value=mock_extract_response)

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
                        "extraction_schema": {"type": "object", "properties": {}},
                        "prompt": "LP",
                        "extraction_config": {"k": "v"},
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "result": {"data": 1},
            "citations": None,
        }
        fake_extraction_client.start_extract.assert_called_once()
        _, kwargs = fake_extraction_client.start_extract.call_args
        assert kwargs["schema"] == {"type": "object", "properties": {}}
        assert kwargs["extraction_config"] == {"k": "v", "generate_citations": True}
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
            ),  # both layout_name and document_layout provided - custom validation
            (
                {
                    "thread_id": "t",
                    "file_name": "f",
                    "extraction_schema": {"type": "object"},
                    "layout_name": "l",
                },
                400,
            ),  # extraction_schema with layout_name - custom validation
            (
                {
                    "thread_id": "t",
                    "file_name": "f",
                    "extraction_schema": {"type": "object"},
                    "data_model_name": "dm",
                },
                400,
            ),  # extraction_schema with data_model_name - custom validation
            (
                {
                    "thread_id": "t",
                    "file_name": "f",
                    "extraction_schema": {"type": "object"},
                    "document_layout": {"name": "a", "data_model_name": "b"},
                },
                400,
            ),  # extraction_schema with document_layout - custom validation
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
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
        fake_extraction_client.upload = AsyncMock(return_value="doc")

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=Mock(
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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

        assert resp.status_code == 400
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.BAD_REQUEST.value.code
        assert "extraction_schema could not be resolved" in err["message"]

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
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=Mock(
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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
            (
                Exception("network"),
                ErrorCode.UNEXPECTED,
                "something went wrong while processing the file",
            ),
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

        thread = Mock(id="t1")
        stored = Mock(file_id="f1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"b")

        # Create a proper Job instance for start_extract return
        mock_job = Mock()
        mock_job.job_id = "extract-job-error"
        mock_job.job_type = JobType.EXTRACT
        # Mock the result method to raise the exception (this is what extract endpoint calls now)
        mock_job.result = AsyncMock(side_effect=raised)

        fake_extraction_client = Mock()
        fake_extraction_client.upload = AsyncMock(return_value="doc")
        fake_extraction_client.extract = AsyncMock(side_effect=raised)
        fake_extraction_client.start_extract = AsyncMock(return_value=mock_job)
        fake_extraction_client.wait_for_job = AsyncMock(side_effect=raised)

        fake_service = Mock()
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(storage_instance, "get_file_by_ref", new=AsyncMock(return_value=stored)),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=Mock(name="dm", prompt=None),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=Mock(
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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

    def test_extract_with_document_layout_success(self, client: TestClient):
        """Test extraction using document_layout with extraction schema."""
        storage_instance = StorageService.get_instance()

        # Use Mock objects instead of SimpleNamespace for proper attribute access
        thread = Mock(id="thread-1")
        stored = Mock(file_id="fid-1", file_ref="ref-1")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"bytes")

        # Create a mock Job instance for start_extract return
        mock_job = Mock()
        mock_job.job_id = "extract-job-raw"
        mock_job.job_type = JobType.EXTRACT

        # Create a mock ExtractResponse object that job.result() will return
        mock_extract_response = Mock(spec=ExtractResponse)
        mock_extract_response.result = [{"extracted": "raw_data"}]
        mock_extract_response.citations = []
        # Mock job.result() to return the extract response
        mock_job.result = AsyncMock(return_value=mock_extract_response)

        fake_extraction_client = Mock()
        fake_extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT = "BASE"
        fake_extraction_client.upload = AsyncMock(return_value="doc-1")
        fake_extraction_client.start_extract = AsyncMock(return_value=mock_job)

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
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
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
            ),
        ):
            resp = client.post(
                "/api/v2/document-intelligence/documents/extract",
                json={
                    "thread_id": "thread-1",
                    "file_name": "file-xyz",
                    "document_layout": {
                        "extraction_schema": {
                            "type": "object",
                            "properties": {"field1": {"type": "string"}},
                        },
                        "prompt": "Custom raw prompt",
                        "extraction_config": {"mode": "raw"},
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "result": {"extracted": "raw_data"},
            "citations": None,
        }

        # Ensure start_extract called with schema and config from document_layout
        fake_extraction_client.start_extract.assert_called_once()
        _, kwargs = fake_extraction_client.start_extract.call_args
        assert kwargs["schema"] == {"type": "object", "properties": {"field1": {"type": "string"}}}
        assert kwargs["extraction_config"] == {"mode": "raw", "generate_citations": True}
        assert kwargs["system_prompt"].startswith("BASE")
        assert "Custom raw prompt" in kwargs["system_prompt"]

        # Ensure we didn't try to look up data models or layouts
        # (since we provided document_layout directly)
        assert len([call for call in fake_service.mock_calls if "DataModel" in str(call)]) == 0

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

        # Create a mock Job that will be returned by start_parse
        mock_job = Mock()
        mock_job.job_id = "parse-job-error"
        mock_job.job_type = JobType.PARSE
        mock_job.result = AsyncMock(side_effect=raised)

        fake_extraction_client = Mock()
        fake_extraction_client.upload = AsyncMock(return_value="https://files.example.com/u/ghi")
        fake_extraction_client.start_parse = AsyncMock(return_value=mock_job)

        with (
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=uploaded),
            ),
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
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
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                new=create_mock_async_extraction_client_class(fake_extraction_client),
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


class TestIngestDocument:
    def _valid_details(self) -> Integration:
        data_server_details = DataServerDetails(
            username="testuser",
            password=SecretString("testpass"),
            data_server_endpoints=[
                DataServerEndpoint(host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP),
                DataServerEndpoint(host="127.0.0.1", port=5432, kind=DataServerEndpointKind.MYSQL),
            ],
        )
        return create_mock_integration_with_data_server_settings(data_server_details)

    def test_ingest_document_success(self, client: TestClient, fastapi_app: FastAPI):
        storage_instance = StorageService.get_instance()

        self._valid_details()

        thread = SimpleNamespace(id="thread-1")
        uploaded = UploadedFile(
            file_id="new-file-999",
            file_path="/tmp/file",
            file_ref="file-ref-999",
            file_hash="h",
            file_size_raw=5,
            mime_type="text/plain",
            created_at=datetime.utcnow(),
            embedded=False,
        )

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_docint_ds = Mock()
        fake_service.get_docint_datasource.return_value = fake_docint_ds

        fake_file_manager = Mock()
        fake_file_manager.upload = AsyncMock(return_value=[uploaded])
        fake_file_manager.read_file_contents = AsyncMock(return_value=b"payload")

        fake_extraction_client = Mock()

        fake_agent_client = Mock()
        fake_di_service = Mock()
        fake_document_result = {"id": "doc-123", "status": "ok"}

        layout = SimpleNamespace(
            extraction_schema={"type": "object"},
            translation_schema={
                "rules": [{"mode": "rename", "source": "field1", "target": "field_one"}]
            },
        )

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch(
                "agent_platform.server.api.dependencies.FileManagerService.get_instance",
                return_value=fake_file_manager,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=SimpleNamespace(name="data-model-1"),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DocumentLayout.find_by_name",
                return_value=layout,
            ),
            patch(
                "agent_platform.server.api.dependencies.get_agent_server_client",
            ) as _get_agent_client,
        ):
            fastapi_app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
            fastapi_app.dependency_overrides[get_di_service] = lambda: fake_di_service
            _get_agent_client.return_value = fake_agent_client
            fake_di_service.document.ingest.return_value = fake_document_result
            resp = client.post(
                "/api/v2/document-intelligence/documents/ingest",
                params={
                    "thread_id": "thread-1",
                    "agent_id": "agent-1",
                    "data_model_name": "data-model-1",
                    "layout_name": "layout-1",
                },
                files={"file": ("test.txt", b"hello", "text/plain")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["document"] == fake_document_result
        assert body["uploaded_file"]["file_id"] == "new-file-999"

    def test_ingest_document_failure_when_thread_not_found(
        self,
        client: TestClient,
        fastapi_app: FastAPI,
    ):
        storage_instance = StorageService.get_instance()

        self._valid_details()

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        fake_file_manager = Mock()
        fake_agent_client = Mock()
        fake_extraction_client = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=None)),
        ):
            fastapi_app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
            fastapi_app.dependency_overrides[get_agent_server_client] = (
                lambda agent_id, request=None, thread_id=None: fake_agent_client
            )
            resp = client.post(
                "/api/v2/document-intelligence/documents/ingest",
                params={
                    "thread_id": "missing-thread",
                    "agent_id": "agent-1",
                    "data_model_name": "dm-1",
                    "layout_name": "layout-1",
                },
                data={"file": "file-ref"},
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "thread missing-thread not found" in err["message"].lower()

    def test_ingest_document_failure_when_file_not_found(
        self,
        client: TestClient,
        fastapi_app: FastAPI,
    ):
        storage_instance = StorageService.get_instance()

        self._valid_details()

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        thread = SimpleNamespace(id="thread-1")

        fake_file_manager = Mock()
        fake_agent_client = Mock()
        fake_extraction_client = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=None),
            ),
        ):
            fastapi_app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
            fastapi_app.dependency_overrides[get_agent_server_client] = (
                lambda agent_id, request=None, thread_id=None: fake_agent_client
            )
            resp = client.post(
                "/api/v2/document-intelligence/documents/ingest",
                params={
                    "thread_id": "thread-1",
                    "agent_id": "agent-1",
                    "data_model_name": "dm-1",
                    "layout_name": "layout-1",
                },
                data={"file": "unknown-file"},
            )

        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.NOT_FOUND.value.code
        assert "file unknown-file not found (storage)" in err["message"].lower()

    def test_ingest_document_failure_when_data_model_not_found(
        self,
        client: TestClient,
        fastapi_app: FastAPI,
    ):
        storage_instance = StorageService.get_instance()

        self._valid_details()

        fake_service = Mock()
        fake_service.ensure_setup.return_value = None
        fake_service.get_docint_datasource.return_value = Mock()

        thread = SimpleNamespace(id="thread-1")
        stored = SimpleNamespace(file_ref="file-ref-123")

        fake_file_manager = Mock()
        fake_file_manager.refresh_file_paths = AsyncMock(return_value=[stored])
        fake_agent_client = Mock()
        fake_extraction_client = Mock()

        with (
            patch.object(
                storage_instance,
                "get_integration_by_kind",
                new=create_mock_get_integration_by_kind(
                    DataServerDetails(
                        username="test",
                        password=SecretString("test"),
                        data_server_endpoints=[
                            DataServerEndpoint(
                                host="127.0.0.1", port=47334, kind=DataServerEndpointKind.HTTP
                            )
                        ],
                    ),
                    "test-api-key",
                ),
            ),
            patch(
                "agent_platform.server.api.dependencies.DocumentIntelligenceService.get_instance",
                return_value=fake_service,
            ),
            patch(
                "agent_platform.server.api.dependencies.AsyncExtractionClient",
                return_value=fake_extraction_client,
            ),
            patch.object(storage_instance, "get_thread", new=AsyncMock(return_value=thread)),
            patch.object(
                storage_instance,
                "get_file_by_ref",
                new=AsyncMock(return_value=stored),
            ),
            patch(
                "agent_platform.server.api.private_v2.document_intelligence.services.DataModel.find_by_name",
                return_value=None,
            ),
        ):
            fastapi_app.dependency_overrides[get_file_manager] = lambda: fake_file_manager
            fastapi_app.dependency_overrides[get_agent_server_client] = (
                lambda agent_id, request=None, thread_id=None: fake_agent_client
            )
            resp = client.post(
                "/api/v2/document-intelligence/documents/ingest",
                params={
                    "thread_id": "thread-1",
                    "agent_id": "agent-1",
                    "data_model_name": "data-model-1",
                    "layout_name": "layout-1",
                },
                data={"file": "file-ref-xyz"},
            )

        assert resp.status_code == 500
        err = resp.json()["error"]
        assert err["code"] == ErrorCode.UNEXPECTED.value.code
