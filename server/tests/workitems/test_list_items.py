"""Tests for the list_work_items endpoint with path variant support."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
)
from agent_platform.server.api.private_v2.work_items import router as work_items_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.constants import SystemConfig
from agent_platform.server.error_handlers import platform_http_error_handler
from agent_platform.server.storage.option import StorageService

from .mock_storage import MockStorage


@pytest.fixture(autouse=True)
def _enable_work_items():
    """Enable work items for the duration of the test."""
    original_instance = SystemConfig._instances.get(SystemConfig)
    SystemConfig.set_instance(SystemConfig(enable_workitems=True))
    yield
    if original_instance is not None:
        SystemConfig.set_instance(original_instance)


@pytest.fixture
def storage() -> MockStorage:
    return MockStorage()


@pytest.fixture
def test_user() -> User:
    return User(
        user_id="123",
        sub="test@test.com",
    )


@pytest.fixture
def system_user() -> User:
    return User(
        user_id="system_user",
        sub="tenant:testing:system:system_user",
    )


@pytest.fixture
def fastapi_app(storage: MockStorage, test_user: User) -> FastAPI:
    """Create FastAPI test app with dependency overrides."""
    app = FastAPI()
    app.include_router(work_items_router, prefix="/work-items")

    # Override dependencies - this is the key to proper FastAPI testing
    app.dependency_overrides[StorageService.get_instance] = lambda: storage
    app.dependency_overrides[auth_user] = lambda: test_user
    app.add_exception_handler(PlatformHTTPError, platform_http_error_handler)  # type: ignore[arg-type]

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)


@pytest.fixture
def sample_work_item(test_user: User, system_user: User) -> WorkItem:
    """Create a sample work item for testing."""
    return WorkItem(
        work_item_id="test-work-item-123",
        user_id=system_user.user_id,
        created_by=test_user.user_id,
        agent_id="test-agent-456",
        status=WorkItemStatus.PENDING,
        messages=[],
        payload={"test": "data"},
    )


class TestListWorkItems:
    """Test cases for the list_work_items endpoint with path variants."""

    @pytest.mark.parametrize(
        "endpoint_path",
        [
            "/work-items",  # Without trailing slash
            "/work-items/",  # With trailing slash
        ],
    )
    async def test_list_work_items_path_variants(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_work_item: WorkItem,
        endpoint_path: str,
    ):
        """Test that both /work-items and /work-items/ return the same work item list."""
        # Setup: Add a work item to the mock storage
        await storage.create_work_item(sample_work_item)

        # Act: Make HTTP GET request to the endpoint
        response = client.get(endpoint_path)

        # Assert: Check the response
        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "records" in response_data
        assert "next_offset" in response_data

        # Verify we got our work item back
        assert len(response_data["records"]) == 1
        work_item_data = response_data["records"][0]
        assert work_item_data["work_item_id"] == sample_work_item.work_item_id
        assert work_item_data["agent_id"] == sample_work_item.agent_id
        assert work_item_data["status"] == sample_work_item.status.value
        assert work_item_data["payload"] == sample_work_item.payload

        # Verify pagination info
        assert response_data["next_offset"] is None  # Only one item, no next page
