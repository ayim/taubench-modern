"""Tests for the create_work_item endpoint with path variant support."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.payloads.create_work_item import CreateWorkItemPayload
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.user import User
from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.api.dependencies import check_work_item_payload_size
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
def test_agent(test_user: User) -> Agent:
    """Create a test agent for work item creation."""
    return Agent(
        agent_id="test-agent-456",
        name="Test Agent",
        description="A test agent for work item creation",
        user_id=test_user.user_id,
        version="1.0.0",
        runbook_structured=Runbook(
            raw_text="Test instructions for the agent",
            content=[],
        ),
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name="default",
            version="1.0.0",
        ),
    )


@pytest.fixture
def fastapi_app(storage: MockStorage, test_user: User, test_agent: Agent) -> FastAPI:
    """Create FastAPI test app with dependency overrides."""
    app = FastAPI()
    app.include_router(work_items_router, prefix="/work-items")

    # Add the test agent to storage
    storage.agents[test_agent.agent_id] = test_agent

    # Override dependencies - this is the key to proper FastAPI testing
    app.dependency_overrides[StorageService.get_instance] = lambda: storage
    app.dependency_overrides[auth_user] = lambda: test_user

    # Override payload size check to avoid QuotasService dependency on real storage
    # This prevents the test from trying to initialize the real SQLiteStorage when
    # check_work_item_payload_size calls QuotasService.get_instance() which in turn
    # calls StorageService.get_instance() directly (bypassing our dependency override)
    async def mock_payload_size_check() -> None:
        """Mock payload size check that always passes for testing."""
        pass

    app.dependency_overrides[check_work_item_payload_size] = mock_payload_size_check
    app.add_exception_handler(PlatformHTTPError, platform_http_error_handler)  # type: ignore[arg-type]

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)


@pytest.fixture
def sample_create_payload(test_agent: Agent) -> CreateWorkItemPayload:
    """Create a sample create work item payload for testing."""
    return CreateWorkItemPayload(
        agent_id=test_agent.agent_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Test message content")],
            )
        ],
        payload={"test": "data", "priority": "high"},
    )


class TestCreateWorkItem:
    """Test cases for the create_work_item endpoint with path variants."""

    @pytest.mark.parametrize(
        "endpoint_path",
        [
            "/work-items",  # Without trailing slash
            "/work-items/",  # With trailing slash
        ],
    )
    def test_create_work_item_path_variants(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_create_payload: CreateWorkItemPayload,
        endpoint_path: str,
    ):
        """Test that both /work-items and /work-items/ create work items successfully."""
        # Act: Make HTTP POST request to the endpoint
        payload_dict = {
            "agent_id": sample_create_payload.agent_id,
            "messages": [msg.model_dump() for msg in sample_create_payload.messages],
            "payload": sample_create_payload.payload,
            "work_item_id": sample_create_payload.work_item_id,
            "callbacks": sample_create_payload.callbacks,
        }
        response = client.post(
            endpoint_path,
            json=payload_dict,
        )

        # Assert: Check the response
        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "work_item_id" in response_data
        assert "agent_id" in response_data
        assert "status" in response_data
        assert "payload" in response_data
        assert "messages" in response_data

        # Verify the work item was created with correct data
        assert response_data["agent_id"] == sample_create_payload.agent_id
        assert response_data["status"] == WorkItemStatus.PENDING.value
        assert response_data["payload"] == sample_create_payload.payload
        assert len(response_data["messages"]) == len(sample_create_payload.messages)
        assert response_data["messages"][0]["content"][0]["text"] == "Test message content"

        # Verify the work item was stored
        work_item_id = response_data["work_item_id"]
        assert work_item_id in storage.work_items

    def test_create_work_item_with_name(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_create_payload: CreateWorkItemPayload,
    ):
        """Test creating a work item with a user-friendly name."""
        # Act: Make HTTP POST request with work_item_name
        payload_dict = {
            "agent_id": sample_create_payload.agent_id,
            "messages": [msg.model_dump() for msg in sample_create_payload.messages],
            "payload": sample_create_payload.payload,
            "work_item_name": "SNOW12345",
        }
        response = client.post("/work-items", json=payload_dict)

        # Assert: Check the response
        assert response.status_code == 200
        response_data = response.json()

        # Verify work_item_name is included in response
        assert "work_item_name" in response_data
        assert response_data["work_item_name"] == "SNOW12345"

        # Verify the work item was stored with the name
        work_item_id = response_data["work_item_id"]
        stored_work_item = storage.work_items[work_item_id]
        assert stored_work_item.work_item_name == "SNOW12345"

    def test_create_work_item_name_validation(
        self,
        client: TestClient,
        storage: MockStorage,
        sample_create_payload: CreateWorkItemPayload,
    ):
        """Test that work_item_name validation works correctly."""
        # Test empty string becomes None
        payload_dict = {
            "agent_id": sample_create_payload.agent_id,
            "messages": [msg.model_dump() for msg in sample_create_payload.messages],
            "payload": sample_create_payload.payload,
            "work_item_name": "   ",  # Only whitespace
        }
        response = client.post("/work-items", json=payload_dict)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["work_item_name"] is None

        # Test whitespace trimming
        payload_dict["work_item_name"] = "  INVABC123  "
        response = client.post("/work-items", json=payload_dict)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["work_item_name"] == "INVABC123"
