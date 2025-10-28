from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.api.public_v2.work_items import router as work_items_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import platform_http_error_handler
from agent_platform.server.storage.option import StorageService

from .mock_storage import MockStorage


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


class TestContinueWorkItem:
    async def test_continue_success(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test successfully continuing a work item from NEEDS_REVIEW to PENDING."""
        # Setup: Create a work item that can be continued
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.NEEDS_REVIEW,  # NEEDS_REVIEW status can be continued
        )
        await storage.create_work_item(work_item)

        # Act: Make HTTP request to continue endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Assert: Check the response
        assert response.status_code == 200  # OK (not 202)
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == "123"
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value

        # Also verify the storage was updated
        updated_item = await storage.get_work_item("123")
        assert updated_item.status == WorkItemStatus.PENDING

    def test_continue_not_found(self, client: TestClient):
        """Test continuing a work item that doesn't exist."""
        response = client.post("/work-items/nonexistent/continue")

        assert response.status_code == 404
        error_data = response.json()
        assert "error" in error_data

    async def test_continue_invalid_transition(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test continuing a work item from an invalid status."""
        # Setup: Create a work item in EXECUTING status (can't continue executing items)
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.EXECUTING,
        )
        await storage.create_work_item(work_item)

        # Act: Try to continue
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Assert: Should get precondition failed
        assert response.status_code == 412  # PRECONDITION_FAILED
        error_data = response.json()
        assert "error" in error_data
        assert "Cannot continue work item from status" in error_data["error"]["message"]

    async def test_continue_metadata_update(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test continuing a work item updates metadata correctly."""
        # Setup: Create a work item that can be continued
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.NEEDS_REVIEW,
        )
        await storage.create_work_item(work_item)

        now = datetime.now(UTC)

        # Act: Make HTTP request to continue endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Check the http response
        assert response.status_code == 200
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == "123"
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value
        assert returned_work_item["status_updated_by"] == WorkItemStatusUpdatedBy.HUMAN.value
        assert returned_work_item["status_updated_at"] >= now.isoformat()

        # Verify that status_updated_* are updated for the requesting user.
        updated_item = await storage.get_work_item("123")
        assert updated_item.status == WorkItemStatus.PENDING
        assert updated_item.status_updated_by == WorkItemStatusUpdatedBy.HUMAN.value
        assert updated_item.status_updated_at >= now

    async def test_continue_from_indeterminate_success(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test successfully continuing a work item from INDETERMINATE to PENDING."""
        # Setup: Create a work item in INDETERMINATE status
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.INDETERMINATE,
        )
        await storage.create_work_item(work_item)

        # Act: Make HTTP request to continue endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Assert: Check the response
        assert response.status_code == 200
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == "123"
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value

        # Also verify the storage was updated
        updated_item = await storage.get_work_item("123")
        assert updated_item.status == WorkItemStatus.PENDING

    @pytest.mark.parametrize(
        "valid_status",
        [
            WorkItemStatus.PRECREATED,
            WorkItemStatus.DRAFT,
            WorkItemStatus.COMPLETED,
            WorkItemStatus.ERROR,
        ],
    )
    async def test_continue_other_valid_transitions(
        self,
        client: TestClient,
        storage: MockStorage,
        test_user: User,
        system_user: User,
        valid_status: WorkItemStatus,
    ):
        """Test continuing from other valid statuses (PRECREATED, COMPLETED, ERROR) succeeds."""
        # Setup: Create a work item in a valid status for continue
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=valid_status,
        )
        await storage.create_work_item(work_item)

        # Act: Continue the work item
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Assert: Should succeed
        assert response.status_code == 200
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == "123"
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value

        # Also verify the storage was updated
        updated_item = await storage.get_work_item("123")
        assert updated_item.status == WorkItemStatus.PENDING

    @pytest.mark.parametrize(
        "invalid_status",
        [
            WorkItemStatus.PENDING,  # PENDING -> PENDING not allowed
            WorkItemStatus.EXECUTING,  # EXECUTING -> PENDING not allowed
            WorkItemStatus.CANCELLED,  # CANCELLED -> anything not allowed (terminal)
        ],
    )
    async def test_continue_invalid_transitions_comprehensive(
        self,
        client: TestClient,
        storage: MockStorage,
        test_user: User,
        system_user: User,
        invalid_status: WorkItemStatus,
    ):
        """Test continuing from various invalid statuses fails with 412."""
        # Setup: Create a work item in an invalid status for continue
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=invalid_status,
        )
        await storage.create_work_item(work_item)

        # Act: Try to continue
        response = client.post(f"/work-items/{work_item.work_item_id}/continue")

        # Assert: Should get precondition failed
        assert response.status_code == 412  # PRECONDITION_FAILED
        error_data = response.json()
        assert "error" in error_data
        assert "Cannot continue work item from status" in error_data["error"]["message"]
