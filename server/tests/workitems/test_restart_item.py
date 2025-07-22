from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
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
        user_id="456",
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


class TestRestartWorkItem:
    async def test_restart_work_item_success(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test successfully restarting a work item."""
        # Setup: Create a work item that can be restarted
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.ERROR,  # ERROR status can be restarted
        )
        storage.create_work_item(work_item)

        # Act: Make HTTP request to restart endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/restart")

        # Assert: Check the response
        assert response.status_code == 200
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == "123"
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value

        # Also verify the storage was updated
        updated_item = await storage.get_work_item("123")
        assert updated_item.status == WorkItemStatus.PENDING

    def test_restart_work_item_not_found(self, client: TestClient):
        """Test restarting a work item that doesn't exist."""
        response = client.post("/work-items/nonexistent/restart")

        assert response.status_code == 404
        error_data = response.json()
        assert "error" in error_data

    def test_restart_work_item_invalid_transition(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test restarting a work item from an invalid status."""
        # Setup: Create a work item in PENDING status (can't restart pending items)
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.PENDING,
        )
        storage.create_work_item(work_item)

        # Act: Try to restart
        response = client.post(f"/work-items/{work_item.work_item_id}/restart")

        # Assert: Should get precondition failed
        assert response.status_code == 412  # PRECONDITION_FAILED
        error_data = response.json()
        assert "error" in error_data
        assert "Cannot restart work item from status" in error_data["error"]["message"]

    async def test_restart_other_users_work_item(
        self, client: TestClient, storage: MockStorage, test_user: User, system_user: User
    ):
        """Test restarting a work item created by another user."""
        # Create a work-item as a user who is different than our mock user
        work_item = WorkItem(
            work_item_id="123",
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id="789",
            status=WorkItemStatus.ERROR,  # ERROR status can be restarted
        )
        storage.create_work_item(work_item)

        now = datetime.now(UTC)

        # Act: Make HTTP request to restart endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/restart")

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

    async def test_restart_work_item(
        self,
        client: TestClient,
        test_user: User,
        storage: MockStorage,
        system_user: User,
    ):
        """Test successful restart from NEEDS_REVIEW state."""
        now = datetime.now(UTC)

        initial_msg = ThreadMessage(
            content=[ThreadTextContent(text="Initial request")], role="user"
        )
        agent_msg = ThreadMessage(content=[ThreadTextContent(text="Agent response")], role="agent")
        work_item = WorkItem(
            work_item_id=str(uuid4()),
            user_id=system_user.user_id,
            created_by=test_user.user_id,
            agent_id=str(uuid4()),
            thread_id=str(uuid4()),
            status=WorkItemStatus.NEEDS_REVIEW,
            initial_messages=[initial_msg],
            messages=[initial_msg, agent_msg],
            payload={},
        )
        storage.create_work_item(work_item)

        # Act: Make HTTP request to restart endpoint
        response = client.post(f"/work-items/{work_item.work_item_id}/restart")

        # Assert: Check the response
        assert response.status_code == 200
        returned_work_item = response.json()
        assert returned_work_item["work_item_id"] == work_item.work_item_id
        assert returned_work_item["status"] == WorkItemStatus.PENDING.value
        assert returned_work_item["status_updated_by"] == WorkItemStatusUpdatedBy.HUMAN.value
        assert returned_work_item["status_updated_at"] >= now.isoformat()
        assert len(returned_work_item["messages"]) == 1
        assert (
            returned_work_item["messages"][0]["content"][0]["text"]
            == initial_msg.content[0].as_text_content()
        )

        updated_item = await storage.get_work_item(work_item.work_item_id)
        assert updated_item.status == WorkItemStatus.PENDING
        assert updated_item.thread_id is None
        assert updated_item.completed_by is None
        assert len(updated_item.messages) == 1
        assert updated_item.messages[0].message_id != initial_msg.message_id, (
            "the new initial message set as the first message should have a unique ID"
        )
        assert (
            updated_item.messages[0].content[0].as_text_content()
            == work_item.initial_messages[0].content[0].as_text_content()
        )
