import os
from http import HTTPStatus
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from agent_platform.core.agent import Agent
from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.file_manager import (
    FileManagerService,
)
from agent_platform.server.storage.option import StorageService
from agent_platform.server.work_items.rest import WorkItemsListResponse


@pytest.fixture
def mock_requests():
    """Mock requests for cloud file manager tests."""
    mock = MagicMock()
    # Mock presigned post response
    mock.post.return_value.status_code = 200
    mock.post.return_value.json.return_value = {
        "url": "https://example.com/upload",
        "form_data": {"key": "value"},
    }
    # Mock presigned get URL response
    mock.get.return_value.status_code = 200
    mock.get.return_value.json.return_value = {
        "url": "https://example.com/download/test-file",
    }
    # Mock file deletion response
    mock.delete.return_value.status_code = 200
    mock.delete.return_value.json.return_value = {"deleted": True}
    # Mock file content download
    mock.get.return_value.content = b"test content"
    return mock


@pytest.fixture(params=["local", "cloud"])
def file_manager_type(request, mock_requests):
    """Parametrized fixture that provides both local and cloud file manager types."""
    manager_type = request.param

    # Reset the FileManagerService to ensure a clean state
    FileManagerService.reset()

    if manager_type == "cloud":
        # Set required environment variable
        os.environ["FILE_MANAGEMENT_API_URL"] = "https://example.com/files"
        with patch("agent_platform.server.file_manager.cloud.requests", mock_requests):
            # Set up cloud file manager
            storage = StorageService.get_instance()
            manager = FileManagerService.get_instance(storage, manager_type="cloud")
            yield manager_type, manager
        # Clean up environment variable
        if "FILE_MANAGEMENT_API_URL" in os.environ:
            del os.environ["FILE_MANAGEMENT_API_URL"]
    else:
        # Set up local file manager
        storage = StorageService.get_instance()
        manager = FileManagerService.get_instance(storage, manager_type="local")
        yield manager_type, manager

    # Clean up after the test
    FileManagerService.reset()


def skip_if_local_for_remote_tests(file_manager_type):
    """Skip test if using local file manager for remote upload/confirm tests."""
    if file_manager_type == "local":
        pytest.skip("Two-stage upload only works with CloudFileManager")


@pytest.mark.asyncio
async def test_create_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test creating a work item."""
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Hello, test message"}]}],
        "payload": {"test_key": "test_value"},
    }

    response = client.post("/api/public/v1/work-items/", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["agent_id"] == seed_agents[0].agent_id
    assert data["thread_id"] is None  # No thread id until the work item is run
    assert data["status"] == WorkItemStatus.PENDING.value
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"][0]["text"] == "Hello, test message"
    assert data["payload"]["test_key"] == "test_value"
    assert "work_item_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_work_item_invalid_agent(client: TestClient):
    """Test creating a work item with invalid agent ID."""
    payload = {
        "agent_id": "invalid-agent",
        "messages": [],
        "payload": {},
    }

    response = client.post("/api/public/v1/work-items/", json=payload)

    assert response.status_code == 400
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "bad_request"
    assert "invalid uuid" in detail["error"]["message"].lower()


@pytest.mark.asyncio
async def test_describe_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test that we can describe a work item."""
    agent_id = seed_agents[0].agent_id

    # Create a work item
    response = client.post(
        "/api/public/v1/work-items",
        json={
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Please help me."}],
                }
            ],
        },
    )
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Get the work item description
    response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert response.status_code == 200

    work_item = response.json()
    assert work_item["work_item_id"] == work_item_id
    assert work_item["agent_id"] == agent_id
    assert work_item["status"] == "PENDING"
    assert "work_item_url" in work_item  # Verify work_item_url field is present
    # Initially should be None since no thread is created yet
    assert work_item["work_item_url"] is None


async def test_work_item_response_includes_work_item_url(client: TestClient, seed_agents: list[Agent]):
    """Test that work item API responses include work_item_url field."""
    agent_id = seed_agents[0].agent_id

    # Create a work item
    response = client.post(
        "/api/public/v1/work-items",
        json={
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Test message"}],
                }
            ],
        },
    )
    assert response.status_code == 200

    work_item = response.json()
    assert "work_item_url" in work_item
    # Should initially be None since no thread is created during work item creation
    assert work_item["work_item_url"] is None

    # List work items should also include work_item_url
    response = client.get("/api/public/v1/work-items")
    assert response.status_code == 200

    work_items = response.json()["records"]
    assert len(work_items) > 0
    for item in work_items:
        assert "work_item_url" in item


@pytest.mark.asyncio
async def test_describe_nonexistent_work_item(client: TestClient):
    """Test describing a work item that doesn't exist."""
    response = client.get("/api/public/v1/work-items/00000000-0000-0000-0000-000000000000")

    # Valid uuid, so not found
    assert response.status_code == 404
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "not_found"
    assert "not found" in detail["error"]["message"].lower()

    response = client.get("/api/public/v1/work-items/invalid-uuid")

    # Invalid uuid, so bad request
    assert response.status_code == 400
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "bad_request"
    assert "invalid uuid" in detail["error"]["message"].lower()


@pytest.mark.asyncio
async def test_list_work_items(client: TestClient, seed_agents: list[Agent]):
    """Test listing work items."""
    # Create multiple work items
    created_work_items = []
    for i in range(3):
        create_payload = {
            "agent_id": seed_agents[i].agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": f"List test message {i}"}],
                }
            ],
            "payload": {"list_index": i},
        }

        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        created_work_items.append(create_response.json())

    # Verify that created work items have messages
    for work_item in created_work_items:
        assert len(work_item["messages"]) == 1
        assert work_item["messages"][0]["role"] == "user"

    # List work items
    response = client.get("/api/public/v1/work-items/")

    assert response.status_code == 200
    data = WorkItemsListResponse.model_validate(response.json())

    assert isinstance(data.records, list)
    assert len(data.records) == 3

    # Check that our created items are in the list
    work_item_ids = {item.work_item_id for item in data.records}
    created_work_item_ids = {item["work_item_id"] for item in created_work_items}

    for work_item_id in created_work_item_ids:
        assert work_item_id in work_item_ids

    # Check that items returned from list endpoint have empty messages
    for listed_work_item in data.records:
        assert listed_work_item.messages == []


@pytest.mark.asyncio
async def test_list_work_items_with_invalid_pagination(
    client: TestClient,
    seed_agents: list[Agent],
):
    """Test listing work items with invalid limit parameter."""
    # Create 5 work items
    for _ in range(5):
        create_payload = {
            "agent_id": seed_agents[0].agent_id,
            "messages": [],
            "payload": {},
        }

        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200

    # Must expect at least one row
    response = client.get("/api/public/v1/work-items/?limit=0&offset=2")
    assert response.status_code == 422

    # Cannot have negative offset
    response = client.get("/api/public/v1/work-items/?limit=2&offset=-1")
    assert response.status_code == 422

    # Cannot have negative limit
    response = client.get("/api/public/v1/work-items/?limit=-1&offset=2")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_work_items_with_pagination(client: TestClient, seed_agents: list[Agent]):
    """Test listing work items with limit/offset parameters."""
    actual = []
    # Create 5 work items
    for _ in range(5):
        create_payload = {
            "agent_id": seed_agents[0].agent_id,
            "messages": [],
            "payload": {},
        }

        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        actual.append(create_response.json()["work_item_id"])

    # List with limit=2 (implicit, offset=0)
    # Items are returned in DESC order by created_at (newest first)
    response = client.get("/api/public/v1/work-items/?limit=2")

    assert response.status_code == 200
    data = WorkItemsListResponse.model_validate(response.json())
    assert len(data.records) == 2
    assert data.records[0].work_item_id == actual[4]
    assert data.records[1].work_item_id == actual[3]
    assert data.next_offset == 2

    response = client.get("/api/public/v1/work-items/?limit=2&offset=2")

    assert response.status_code == 200
    data = WorkItemsListResponse.model_validate(response.json())
    assert len(data.records) == 2
    assert data.records[0].work_item_id == actual[2]
    assert data.records[1].work_item_id == actual[1]
    assert data.next_offset == 4

    response = client.get("/api/public/v1/work-items/?limit=2&offset=4")
    assert response.status_code == 200
    data = WorkItemsListResponse.model_validate(response.json())
    assert len(data.records) == 1
    assert data.records[0].work_item_id == actual[0]
    assert data.next_offset is None


@pytest.mark.asyncio
async def test_cancel_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test canceling a work item."""
    # First create a work item
    create_payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [
            {
                "role": "user",
                "content": [{"kind": "text", "text": "This item will be canceled"}],
            }
        ],
        "payload": {"cancel_test": True},
    }

    create_response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # Verify the item exists before canceling
    get_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200

    # Cancel the work item
    cancel_response = client.post(f"/api/public/v1/work-items/{work_item_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "ok"

    # Verify the item is deleted (based on current cancel implementation)
    get_response_after = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert get_response_after.status_code == 200
    item_after_cancel = get_response_after.json()
    assert item_after_cancel["work_item_id"] == work_item_id
    assert item_after_cancel["status"] == WorkItemStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_nonexistent_work_item(client: TestClient):
    """Test canceling a work item that doesn't exist."""
    response = client.post("/api/public/v1/work-items/00000000-0000-0000-0000-000000000000/cancel")
    assert response.status_code == HTTPStatus.NOT_FOUND.value


@pytest.mark.asyncio
async def test_full_workflow(client: TestClient, seed_agents: list[Agent]):
    """Test a complete workflow: create -> describe -> list -> cancel."""
    # 1. Create
    create_payload = {
        "agent_id": seed_agents[1].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Full workflow test"}]}],
        "payload": {"workflow": "complete"},
    }

    create_response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # 2. Describe
    describe_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert describe_response.status_code == 200
    described_item = describe_response.json()
    assert described_item["work_item_id"] == work_item_id
    assert described_item["agent_id"] == seed_agents[1].agent_id

    # 3. List (should contain our item)
    list_response = client.get("/api/public/v1/work-items/")
    assert list_response.status_code == 200
    items = WorkItemsListResponse.model_validate(list_response.json())
    item_ids = [item.work_item_id for item in items.records]
    assert work_item_id in item_ids

    # Check that items returned from list endpoint have empty messages
    for listed_work_item in items.records:
        assert listed_work_item.messages == []

    # 4. Cancel
    cancel_response = client.post(f"/api/public/v1/work-items/{work_item_id}/cancel")
    assert cancel_response.status_code == 200

    # 5. Verify cancellation
    final_describe_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert final_describe_response.status_code == 200
    final_describe_item = final_describe_response.json()
    assert final_describe_item["work_item_id"] == work_item_id
    assert final_describe_item["status"] == WorkItemStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_upload_file_to_work_item(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test uploading a file to a work item."""
    manager_type, manager = file_manager_type

    # Create a test file
    test_content = b"This is test file content for work item"
    test_file = ("test_file.txt", BytesIO(test_content), "text/plain")

    # Upload file without work_item_id (should create new work item)
    response = client.post("/api/public/v1/work-items/upload-file", files={"file": test_file})

    assert response.status_code == 200
    data = response.json()
    assert "work_item_id" in data
    work_item_id = data["work_item_id"]

    # Verify work item was created in DRAFT state
    get_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200
    work_item = get_response.json()
    assert work_item["status"] == WorkItemStatus.DRAFT.value
    assert work_item["agent_id"] is None  # No agent assigned yet


@pytest.mark.asyncio
async def test_upload_file_to_existing_work_item(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test uploading a file to an existing work item."""
    manager_type, manager = file_manager_type
    # First create a work item in DRAFT state
    test_file1 = ("file1.txt", BytesIO(b"First file content"), "text/plain")

    response = client.post("/api/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Upload another file to the same work item
    test_file2 = ("file2.txt", BytesIO(b"Second file content"), "text/plain")

    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        files={"file": test_file2},
    )

    assert response.status_code == 200
    assert response.json()["work_item_id"] == work_item_id


@pytest.mark.asyncio
async def test_upload_duplicate_file_name_to_work_item(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test uploading a file with duplicate name to work item should fail."""
    manager_type, manager = file_manager_type
    # Create work item with first file
    test_file1 = ("duplicate.txt", BytesIO(b"First content"), "text/plain")

    response = client.post("/api/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to upload file with same name
    test_file2 = ("duplicate.txt", BytesIO(b"Second content"), "text/plain")

    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        files={"file": test_file2},
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_file_to_nonexistent_work_item(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test uploading a file to a non-existent work item should fail."""
    manager_type, manager = file_manager_type
    test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")
    fake_work_item_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={fake_work_item_id}",
        files={"file": test_file},
    )

    assert response.status_code == 404
    assert "A work item with the given ID was not found" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_file_to_non_draft_work_item(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test uploading a file to a work item not in DRAFT state should fail."""
    manager_type, manager = file_manager_type
    # Create a work item with agent (will be in PENDING state)
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message"}]}],
        "payload": {},
    }

    response = client.post("/api/public/v1/work-items/", json=payload)
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to upload file to PENDING work item
    test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")

    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        files={"file": test_file},
    )

    assert response.status_code == 400
    assert "Files can only be attached to work-items in the DRAFT state." in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_with_files_workflow(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test complete workflow: upload files -> create work item -> verify files copied to thread."""
    manager_type, manager = file_manager_type
    # 1. Upload files to create work item
    test_file1 = ("document.txt", BytesIO(b"Important document content"), "text/plain")
    test_file2 = ("data.csv", BytesIO(b"col1,col2\nval1,val2"), "text/csv")

    # Upload first file
    response = client.post("/api/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Upload second file to same work item
    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        files={"file": test_file2},
    )
    assert response.status_code == 200

    # 2. Convert work item to PENDING by adding agent and messages
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Process these files"}]}],
        "payload": {"task": "file_processing"},
        "work_item_id": work_item_id,
    }

    response = client.post("/api/public/v1/work-items/", json=payload)
    assert response.status_code == 200
    work_item = response.json()

    # Verify work item has agent and is PENDING
    assert work_item["agent_id"] == seed_agents[0].agent_id
    assert work_item["status"] == WorkItemStatus.PENDING.value
    assert work_item["work_item_id"] == work_item_id

    # Verify messages include the uploaded files (this would happen during background processing)
    # Note: In real workflow, files get copied to thread and file upload messages are added
    assert len(work_item["messages"]) == 1  # Our user message
    assert work_item["messages"][0]["content"][0]["text"] == "Process these files"


@pytest.mark.asyncio
async def test_create_describe_and_list_work_item_with_callback(client: TestClient, seed_agents: list[Agent]):
    """Test creating a work item with callback, then describing and listing to
    verify callbacks are included."""
    # Create a work item with a callback
    create_payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message with callback"}]}],
        "payload": {"test_key": "test_value"},
        "callbacks": [
            {
                "url": "https://example.com/webhook",
                "signature_secret": "secret123",
                "on_status": "NEEDS_REVIEW",
            }
        ],
    }

    create_response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    created_work_item = create_response.json()
    work_item_id = created_work_item["work_item_id"]

    # Verify callback was stored correctly in creation response
    assert len(created_work_item["callbacks"]) == 1
    callback = created_work_item["callbacks"][0]
    assert callback["url"] == "https://example.com/webhook"
    assert callback["signature_secret"] == "secret123"
    assert callback["on_status"] == "NEEDS_REVIEW"

    # Test describe endpoint includes callbacks
    describe_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert describe_response.status_code == 200
    described_work_item = describe_response.json()
    assert len(described_work_item["callbacks"]) == 1
    described_callback = described_work_item["callbacks"][0]
    assert described_callback["url"] == "https://example.com/webhook"
    assert described_callback["signature_secret"] == "secret123"
    assert described_callback["on_status"] == "NEEDS_REVIEW"

    # Test list endpoint includes callbacks
    list_response = client.get("/api/public/v1/work-items/")
    assert list_response.status_code == 200
    work_items = WorkItemsListResponse.model_validate(list_response.json())

    # Find our work item in the list
    target_work_item = None
    for item in work_items.records:
        if item.work_item_id == work_item_id:
            target_work_item = item
            break

    assert target_work_item is not None
    assert len(target_work_item.callbacks) == 1
    listed_callback = target_work_item.callbacks[0]
    assert listed_callback.url == "https://example.com/webhook"
    assert listed_callback.signature_secret == "secret123"
    assert listed_callback.on_status == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_create_work_item_with_multiple_callbacks(client: TestClient, seed_agents: list[Agent]):
    """Test creating a work item with multiple callbacks for different statuses."""
    create_payload = {
        "agent_id": seed_agents[1].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Multiple callbacks test"}]}],
        "payload": {"multi_callback": True},
        "callbacks": [
            {
                "url": "https://example.com/error",
                "signature_secret": "secret_error",
                "on_status": "ERROR",
            },
            {
                "url": "https://example.com/needs_review",
                "on_status": "NEEDS_REVIEW",
            },
        ],
    }

    response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert response.status_code == 200
    work_item = response.json()

    # Verify all callbacks were stored
    assert len(work_item["callbacks"]) == 2

    # Check each callback
    callbacks_by_status = {cb["on_status"]: cb for cb in work_item["callbacks"]}

    error_callback = callbacks_by_status["ERROR"]
    assert error_callback["url"] == "https://example.com/error"
    assert error_callback["signature_secret"] == "secret_error"

    needs_review_callback = callbacks_by_status["NEEDS_REVIEW"]
    assert needs_review_callback["url"] == "https://example.com/needs_review"
    assert needs_review_callback["signature_secret"] is None


@pytest.mark.parametrize(
    ("callback_config", "expected_status"),
    [
        pytest.param({"url": "", "on_status": "COMPLETED"}, HTTPStatus.BAD_REQUEST, id="empty_url"),
        pytest.param(
            {"url": "https://example.com/webhook", "on_status": "INVALID_STATUS"},
            HTTPStatus.UNPROCESSABLE_ENTITY,
            id="invalid_status",
        ),
    ],
)
@pytest.mark.asyncio
async def test_create_work_item_with_invalid_callbacks(
    client: TestClient, seed_agents: list[Agent], callback_config: dict, expected_status: HTTPStatus
):
    """Test validation of invalid callback configurations."""
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test invalid callback"}]}],
        "payload": {},
        "callbacks": [callback_config],
    }

    response = client.post("/api/public/v1/work-items/", json=payload)
    assert response.status_code == expected_status.value
    error_detail = response.json()
    assert "error" in error_detail


@pytest.mark.asyncio
async def test_cannot_create_multiple_callbacks_for_same_status(client: TestClient, seed_agents: list[Agent]):
    """Test creating a work item with multiple callbacks for the same status."""
    # Create a work item with a callback
    create_payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message with callback"}]}],
        "payload": {"test_key": "test_value"},
        "callbacks": [
            {
                "url": "https://example.com/webhook1",
                "signature_secret": "secret123",
                "on_status": "NEEDS_REVIEW",
            },
            {
                "url": "https://example.com/webhook2",
                "signature_secret": "secret123",
                "on_status": "NEEDS_REVIEW",
            },
        ],
    }

    create_response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == HTTPStatus.BAD_REQUEST.value


@pytest.mark.asyncio
async def test_work_item_request_remote_file_upload_new_work_item(client: TestClient, file_manager_type):
    """Test requesting remote file upload that creates a new work item."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # Request upload without work_item_id (should create new one)
    response = client.post(
        "/api/public/v1/work-items/upload-file",
        data={"file": "test.pdf"},  # String parameter for remote upload
    )

    assert response.status_code == 200
    data = response.json()

    # Should return work item ID and upload details
    assert "work_item_id" in data
    assert "upload_url" in data
    assert "upload_form_data" in data
    assert "file_id" in data
    assert "file_ref" in data

    work_item_id = data["work_item_id"]

    # Verify work item was created in DRAFT state
    get_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200
    work_item = get_response.json()
    assert work_item["status"] == WorkItemStatus.DRAFT.value
    assert work_item["agent_id"] is None


@pytest.mark.asyncio
async def test_work_item_request_remote_file_upload_existing_work_item(client: TestClient, file_manager_type):
    """Test requesting remote file upload for existing work item."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # First create a work item via file upload
    response = client.post("/api/public/v1/work-items/upload-file", data={"file": "first.txt"})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Request upload for existing work item
    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        data={"file": "second.txt"},
    )

    assert response.status_code == 200
    data = response.json()

    # Should return same work item ID
    assert data["work_item_id"] == work_item_id
    assert "upload_url" in data
    assert "upload_form_data" in data
    assert "file_id" in data
    assert "file_ref" in data


@pytest.mark.asyncio
async def test_work_item_request_remote_file_upload_invalid_work_item(client: TestClient, file_manager_type):
    """Test requesting remote file upload for non-existent work item."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    fake_work_item_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={fake_work_item_id}",
        data={"file": "test.txt"},
    )

    assert response.status_code == 404
    assert "A work item with the given ID was not found" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_request_remote_file_upload_non_draft_work_item(
    client: TestClient, seed_agents: list[Agent], file_manager_type
):
    """Test requesting remote file upload for work item not in DRAFT state."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # Create work item directly in PENDING state
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message"}]}],
        "payload": {},
    }

    response = client.post("/api/public/v1/work-items/", json=payload)
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to request upload for PENDING work item
    response = client.post(
        f"/api/public/v1/work-items/upload-file?work_item_id={work_item_id}",
        data={"file": "test.txt"},
    )

    assert response.status_code == 400
    assert "Files can only be attached to work-items in the DRAFT state." in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_confirm_remote_file_upload(client: TestClient, file_manager_type):
    """Test confirming a remote file upload."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # First request upload
    response = client.post("/api/public/v1/work-items/upload-file", data={"file": "test.pdf"})
    assert response.status_code == 200
    data = response.json()
    work_item_id = data["work_item_id"]
    file_id = data["file_id"]
    file_ref = data["file_ref"]

    # Confirm the upload
    confirm_payload = {"file_ref": file_ref, "file_id": file_id}

    response = client.post(f"/api/public/v1/work-items/{work_item_id}/confirm-file", json=confirm_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["work_item_id"] == work_item_id


@pytest.mark.asyncio
async def test_work_item_confirm_remote_file_upload_missing_work_item(client: TestClient, file_manager_type):
    """Test confirming remote file upload for non-existent work item."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    fake_work_item_id = "00000000-0000-0000-0000-000000000000"

    confirm_payload = {"file_ref": "test.pdf", "file_id": "fake-file-id"}

    response = client.post(f"/api/public/v1/work-items/{fake_work_item_id}/confirm-file", json=confirm_payload)

    assert response.status_code == 404
    assert "A work item with the given ID was not found" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_confirm_remote_file_upload_non_draft_work_item(
    client: TestClient, seed_agents: list[Agent], file_manager_type
):
    """Test confirming remote file upload for work item not in DRAFT state."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # Create work item directly in PENDING state
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message"}]}],
        "payload": {},
    }

    response = client.post("/api/public/v1/work-items/", json=payload)
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to confirm upload for PENDING work item
    confirm_payload = {"file_ref": "test.pdf", "file_id": "fake-file-id"}

    response = client.post(f"/api/public/v1/work-items/{work_item_id}/confirm-file", json=confirm_payload)

    assert response.status_code == 400
    assert "Files can only be attached to work-items in the DRAFT state." in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_two_stage_file_upload_workflow(
    client: TestClient, seed_agents: list[Agent], file_manager_type
):
    """Test complete two-stage file upload workflow: request -> upload -> confirm -> process."""

    skip_if_local_for_remote_tests(file_manager_type)

    agent = seed_agents[0]

    # 1. Request remote upload (creates work item in DRAFT state)
    request_payload = {"file": "important-document.pdf"}
    request_response = client.post("/api/public/v1/work-items/upload-file", data=request_payload)
    assert request_response.status_code == 200

    request_data = request_response.json()
    work_item_id = request_data["work_item_id"]
    file_id = request_data["file_id"]
    file_ref = request_data["file_ref"]

    # Verify work item is in DRAFT state
    get_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200
    work_item = get_response.json()
    assert work_item["status"] == WorkItemStatus.DRAFT.value
    assert work_item["agent_id"] is None

    # 2. Simulate cloud upload (this would normally be done by client to cloud storage)
    # For testing purposes, we'll skip the actual upload to cloud storage

    # 3. Confirm the upload
    confirm_payload = {"file_ref": file_ref, "file_id": file_id}
    confirm_response = client.post(f"/api/public/v1/work-items/{work_item_id}/confirm-file", json=confirm_payload)
    assert confirm_response.status_code == 200
    confirm_data = confirm_response.json()
    assert confirm_data["work_item_id"] == work_item_id

    # 4. Convert work item to PENDING by adding agent and messages
    create_payload = {
        "agent_id": agent.agent_id,
        "messages": [
            {
                "role": "user",
                "content": [{"kind": "text", "text": "Analyze the uploaded document"}],
            }
        ],
        "payload": {"task": "document_analysis"},
        "work_item_id": work_item_id,
    }

    create_response = client.post("/api/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()

    # Verify work item is now PENDING with agent
    assert work_item["status"] == WorkItemStatus.PENDING.value
    assert work_item["agent_id"] == agent.agent_id
    assert work_item["work_item_id"] == work_item_id


@pytest.mark.asyncio
async def test_complete_work_item_from_valid_statuses(client: TestClient, seed_agents: list[Agent]):
    """Test completing work items from all valid statuses."""
    from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB
    from agent_platform.server.storage.option import StorageService

    storage = StorageService.get_instance()
    system_user, _ = await storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)

    valid_from_statuses = [
        WorkItemStatus.EXECUTING,
        WorkItemStatus.NEEDS_REVIEW,
        WorkItemStatus.INDETERMINATE,
        WorkItemStatus.ERROR,
    ]

    for from_status in valid_from_statuses:
        # Create a new work item for each test
        create_payload = {
            "agent_id": seed_agents[0].agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "kind": "text",
                            "text": f"This item will be completed from {from_status.value}",
                        }
                    ],
                }
            ],
            "payload": {"complete_test": True, "from_status": from_status.value},
        }

        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        work_item = create_response.json()
        work_item_id = work_item["work_item_id"]

        # Move the work item to the target status
        await storage.update_work_item_status(system_user.user_id, work_item_id, from_status)

        # Verify the item is in the expected status
        get_response = client.get(f"/api/public/v1/work-items/{work_item_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == from_status.value

        # Complete the work item
        complete_response = client.post(f"/api/public/v1/work-items/{work_item_id}/complete")
        assert complete_response.status_code == 200, f"Failed to complete from {from_status.value}"
        assert complete_response.json()["status"] == "ok"

        # Verify the item is now COMPLETED
        get_response_after = client.get(f"/api/public/v1/work-items/{work_item_id}")
        assert get_response_after.status_code == 200
        item_after_complete = get_response_after.json()
        assert item_after_complete["work_item_id"] == work_item_id
        assert item_after_complete["status"] == WorkItemStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_confirm_file_attachment_size_quota_validation(
    client: TestClient, seed_agents: list[Agent], file_manager_type
):
    """Test that confirm_file endpoint validates file attachment size against quota limits."""
    manager_type, manager = file_manager_type

    # This test only works with direct file uploads, not remote uploads
    if manager_type != "local":
        pytest.skip("File attachment size validation only applies to direct uploads")

    # Mock QuotasService to return very small file attachment limit
    with patch("agent_platform.core.configurations.quotas.QuotasService.get_instance") as mock_quotas:
        mock_service = Mock()
        mock_service.get_max_work_item_payload_size.return_value = 1000  # 1000 KB payload limit
        mock_service.get_max_work_item_file_attachment_size.return_value = 0.001  # 1 KB file limit
        mock_quotas.return_value = mock_service

        # Upload a file larger than 1 KB
        large_content = b"x" * 2048  # 2 KB file
        test_file = ("large_file.txt", BytesIO(large_content), "text/plain")
        response = client.post("/api/public/v1/work-items/upload-file", files={"file": test_file})

        # Should fail with 400 due to file attachment size quota exceeded
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_confirm_file_quota_validation_success(client: TestClient, seed_agents: list[Agent], file_manager_type):
    """Test that confirm_file endpoint succeeds when within quota limits."""
    manager_type, manager = file_manager_type
    skip_if_local_for_remote_tests(manager_type)

    # First create a work item with remote file upload request
    request_payload = {"file": "test.pdf"}
    request_response = client.post("/api/public/v1/work-items/upload-file", data=request_payload)
    assert request_response.status_code == 200

    request_data = request_response.json()
    work_item_id = request_data["work_item_id"]
    file_id = request_data["file_id"]
    file_ref = request_data["file_ref"]

    # Mock QuotasService to return generous limits
    with patch("agent_platform.core.configurations.quotas.QuotasService.get_instance") as mock_quotas:
        mock_service = Mock()
        mock_service.get_max_work_item_payload_size.return_value = 1000  # 1000 KB payload limit
        mock_service.get_max_work_item_file_attachment_size.return_value = 100  # 100 MB file limit
        mock_quotas.return_value = mock_service

        confirm_payload = {"file_ref": file_ref, "file_id": file_id}
        confirm_response = client.post(f"/api/public/v1/work-items/{work_item_id}/confirm-file", json=confirm_payload)

        # Should succeed
        assert confirm_response.status_code == 200
        confirm_data = confirm_response.json()
        assert confirm_data["work_item_id"] == work_item_id


@pytest.mark.asyncio
async def test_get_work_items_summary(client: TestClient, seed_agents: list[Agent]):
    """Test getting work items summary grouped by agent and status."""
    # Create work items with different statuses for different agents
    created_work_items = []

    # Create work items for first agent
    for i in range(2):
        create_payload = {
            "agent_id": seed_agents[0].agent_id,
            "agent_name": seed_agents[0].name,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": f"Summary test message {i}"}],
                }
            ],
            "payload": {"summary_index": i},
        }
        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        created_work_items.append(create_response.json())

    # Create work items for second agent
    for i in range(2):
        create_payload = {
            "agent_id": seed_agents[1].agent_id,
            "agent_name": seed_agents[1].name,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": f"Summary test message {i}"}],
                }
            ],
            "payload": {"summary_index": i},
        }
        create_response = client.post("/api/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        created_work_items.append(create_response.json())

    # Get summary
    response = client.get("/api/v2/work-items/summary")

    assert response.status_code == 200
    data = response.json()

    # Should be a list of agent summaries
    assert isinstance(data, list)
    assert len(data) == 2  # Two agents with work items

    # Check structure of each agent summary
    for agent_summary in data:
        assert "agent_id" in agent_summary
        assert "agent_name" in agent_summary
        assert "work_items_status_counts" in agent_summary

        # Check that agent_id matches one of our seed agents
        agent_ids = {agent.agent_id for agent in seed_agents}
        assert agent_summary["agent_id"] in agent_ids

        # Check that work_items_status_counts is a dict
        assert isinstance(agent_summary["work_items_status_counts"], dict)

        # Check that each status has a count (integer)
        for _status, count in agent_summary["work_items_status_counts"].items():
            assert isinstance(count, int)
            assert count >= 0

    # Verify that the total count matches the number of created work items
    total_count = 0
    for agent_summary in data:
        for _status, count in agent_summary["work_items_status_counts"].items():
            total_count += count

    assert total_count == len(created_work_items)


@pytest.mark.asyncio
async def test_get_work_items_summary_empty(client: TestClient):
    """Test getting work items summary when no work items exist."""
    response = client.get("/api/v2/work-items/summary")

    assert response.status_code == 200
    data = response.json()

    # Should be an empty list
    assert isinstance(data, list)
    assert len(data) == 0
