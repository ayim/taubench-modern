"""Tests for the list_work_items endpoint with path variant support."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
)
from agent_platform.server.api.public_v2.work_items import router as work_items_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.constants import SystemConfig
from agent_platform.server.error_handlers import platform_http_error_handler
from agent_platform.server.storage.option import StorageService

from .mock_storage import MockStorage


def _create_test_agent(
    agent_id: str,
    name: str,
    description: str,
    user_id: str,
) -> "Agent":
    """Helper to create a test agent with standard configuration."""

    return Agent(
        agent_id=agent_id,
        name=name,
        description=description,
        user_id=user_id,
        runbook_structured=Runbook(raw_text="Test instructions for the agent", content=[]),
        version="1.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="default", version="1.0"),
        action_packages=[],
        mcp_servers=[],
        mcp_server_ids=[],
        platform_params_ids=[],
    )


def _create_test_work_item(  # noqa: PLR0913
    work_item_id: str,
    user_id: str,
    created_by: str,
    agent_id: str,
    status: WorkItemStatus = WorkItemStatus.PENDING,
    work_item_name: str | None = None,
    payload: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> WorkItem:
    """Helper to create a test work item with standard configuration."""
    return WorkItem(
        work_item_id=work_item_id,
        user_id=user_id,
        created_by=created_by,
        agent_id=agent_id,
        status=status,
        work_item_name=work_item_name,
        messages=[],
        payload=payload or {},
        created_at=created_at or datetime.now(UTC),
        updated_at=updated_at or datetime.now(UTC),
    )


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

    async def test_list_work_items_with_status_filter(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_work_item: WorkItem,
    ):
        """Test filtering work items by status."""
        # Create work items with different statuses
        pending_item = _create_test_work_item(
            work_item_id="pending-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id=sample_work_item.agent_id or "",
            status=WorkItemStatus.PENDING,
        )
        completed_item = _create_test_work_item(
            work_item_id="completed-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id=sample_work_item.agent_id or "",
            status=WorkItemStatus.COMPLETED,
        )

        await storage.create_work_item(pending_item)
        await storage.create_work_item(completed_item)

        # Test filtering by PENDING status
        response = client.get("/work-items?work_item_status=PENDING")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == pending_item.work_item_id

        # Test filtering by COMPLETED status
        response = client.get("/work-items?work_item_status=COMPLETED")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == completed_item.work_item_id

        # Verify that an unknown status is rejected
        response = client.get("/work-items?work_item_status=BOGUS")
        assert response.status_code == 422

        # Test filtering by multiple statuses
        response = client.get("/work-items?work_item_status=PENDING&work_item_status=COMPLETED")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 2
        work_item_ids = {item["work_item_id"] for item in response_data["records"]}
        assert pending_item.work_item_id in work_item_ids
        assert completed_item.work_item_id in work_item_ids

    async def test_list_work_items_with_search_filter(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_work_item: WorkItem,
    ):
        """Test searching work items by work item name only."""
        # Create work items with different names
        search_item = _create_test_work_item(
            work_item_id="search-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id="search-agent",
            work_item_name="Search Test Work Item",
        )
        other_item = _create_test_work_item(
            work_item_id="other-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id="other-agent",
            work_item_name="Other Work Item",
        )

        await storage.create_work_item(search_item)
        await storage.create_work_item(other_item)

        # Test searching by work item name
        response = client.get("/work-items?name_search=Search Test")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == search_item.work_item_id

        # Test searching by partial work item name
        response = client.get("/work-items?name_search=Work Item")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 2
        work_item_ids = {item["work_item_id"] for item in response_data["records"]}
        assert search_item.work_item_id in work_item_ids
        assert other_item.work_item_id in work_item_ids

        # Test case-insensitive search
        response = client.get("/work-items?name_search=search test")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == search_item.work_item_id

    async def test_list_work_items_with_combined_filters(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_work_item: WorkItem,
    ):
        """Test combining status and name search filters."""
        # Create work items with different statuses and names
        pending_search_item = _create_test_work_item(
            work_item_id="pending-search-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id="combined-agent",
            status=WorkItemStatus.PENDING,
            work_item_name="Pending Search Item",
        )
        completed_search_item = _create_test_work_item(
            work_item_id="completed-search-item",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id="combined-agent",
            status=WorkItemStatus.COMPLETED,
            work_item_name="Completed Search Item",
        )

        await storage.create_work_item(pending_search_item)
        await storage.create_work_item(completed_search_item)

        # Test combined filtering with PENDING status
        response = client.get("/work-items?work_item_status=PENDING&name_search=Search")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == pending_search_item.work_item_id

        # Test with COMPLETED status
        response = client.get("/work-items?work_item_status=COMPLETED&name_search=Search")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 1
        assert response_data["records"][0]["work_item_id"] == completed_search_item.work_item_id

        # Test with multiple statuses
        response = client.get(
            "/work-items?work_item_status=PENDING&work_item_status=COMPLETED&name_search=Search"
        )
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) == 2
        work_item_ids = {item["work_item_id"] for item in response_data["records"]}
        assert pending_search_item.work_item_id in work_item_ids
        assert completed_search_item.work_item_id in work_item_ids

    async def test_list_work_items_ordering_by_updated_at(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_work_item: WorkItem,
    ):
        now = datetime.now(UTC)
        """Test that work items are ordered by updated_at DESC."""
        # Create two work items
        item1 = _create_test_work_item(
            work_item_id="item1",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id=sample_work_item.agent_id or "",
            created_at=now,
            updated_at=now,
        )
        # Windows clocks appear to be less accurate and won't pick up on the small difference
        # that naturally occurs. Explicitly force created_at/updated_at times.
        then = now + timedelta(seconds=1)
        item2 = _create_test_work_item(
            work_item_id="item2",
            user_id=sample_work_item.user_id,
            created_by=sample_work_item.created_by,
            agent_id=sample_work_item.agent_id or "",
            created_at=then,
            updated_at=then,
        )

        await storage.create_work_item(item1)
        await storage.create_work_item(item2)

        # Update item2 to have a more recent updated_at
        await storage.update_work_item_status(
            sample_work_item.user_id, item2.work_item_id, WorkItemStatus.COMPLETED
        )

        # Get items and verify ordering
        response = client.get("/work-items")
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["records"]) >= 2

        # verify that item1 does not have a more-recent updated_at than item2
        assert item2.updated_at > item1.updated_at

        # item2 should come before item1 due to more recent updated_at
        assert response_data["records"][0]["work_item_id"] == item2.work_item_id
        assert response_data["records"][1]["work_item_id"] == item1.work_item_id
