import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.errors.responses import ErrorCode
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
