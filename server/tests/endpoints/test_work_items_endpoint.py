from http import HTTPStatus
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from agent_platform.core.agent import Agent
from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.constants import SystemConfig


@pytest.fixture(autouse=True)
def _enable_work_items():
    """Enable work items for the duration of the test."""
    original_instance = SystemConfig._instances.get(SystemConfig)
    SystemConfig.set_instance(SystemConfig(enable_workitems=True))
    yield
    if original_instance is not None:
        SystemConfig.set_instance(original_instance)


@pytest.mark.asyncio
async def test_create_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test creating a work item."""
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Hello, test message"}]}
        ],
        "payload": {"test_key": "test_value"},
    }

    response = client.post("/public/v1/work-items/", json=payload)

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

    response = client.post("/public/v1/work-items/", json=payload)

    assert response.status_code == 400
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "bad_request"
    assert "invalid uuid" in detail["error"]["message"].lower()


@pytest.mark.asyncio
async def test_describe_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test describing a work item with results included."""
    # First create a work item
    create_payload = {
        "agent_id": seed_agents[1].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Test message with results"}]}
        ],
        "payload": {},
    }

    create_response = client.post("/public/v1/work-items/", json=create_payload)
    work_item_id = create_response.json()["work_item_id"]

    # Get work item with results=true (return messages)
    response = client.get(f"/public/v1/work-items/{work_item_id}?results=true")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 1  # Messages should be included
    assert data["messages"][0]["content"][0]["kind"] == "text"
    assert data["messages"][0]["content"][0]["text"] == "Test message with results"

    # Get work item with results=false (default, no messages)
    response = client.get(f"/public/v1/work-items/{work_item_id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 0  # Messages should not be included


@pytest.mark.asyncio
async def test_describe_nonexistent_work_item(client: TestClient):
    """Test describing a work item that doesn't exist."""
    response = client.get("/public/v1/work-items/00000000-0000-0000-0000-000000000000")

    # Valid uuid, so not found
    assert response.status_code == 404
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "not_found"
    assert "not found" in detail["error"]["message"].lower()

    response = client.get("/public/v1/work-items/invalid-uuid")

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

        create_response = client.post("/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        created_work_items.append(create_response.json())

    # Verify that created work items have messages
    for work_item in created_work_items:
        assert len(work_item["messages"]) == 1
        assert work_item["messages"][0]["role"] == "user"

    # List work items
    response = client.get("/public/v1/work-items/")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 3

    # Check that our created items are in the list
    work_item_ids = {item["work_item_id"] for item in data}
    created_work_item_ids = {item["work_item_id"] for item in created_work_items}

    for work_item_id in created_work_item_ids:
        assert work_item_id in work_item_ids

    # Check that items returned from list endpoint have empty messages
    for listed_work_item in data:
        assert listed_work_item["messages"] == []


@pytest.mark.asyncio
async def test_list_work_items_with_limit(client: TestClient, seed_agents: list[Agent]):
    """Test listing work items with limit parameter."""
    # Create 5 work items
    for _ in range(5):
        create_payload = {
            "agent_id": seed_agents[0].agent_id,
            "messages": [],
            "payload": {},
        }

        create_response = client.post("/public/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200

    # List with limit=2
    response = client.get("/public/v1/work-items/?limit=2")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2

    # Check that items returned from list endpoint have empty messages
    for listed_work_item in data:
        assert listed_work_item["messages"] == []


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

    create_response = client.post("/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # Verify the item exists before canceling
    get_response = client.get(f"/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200

    # Cancel the work item
    cancel_response = client.post(f"/public/v1/work-items/{work_item_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "ok"

    # Verify the item is deleted (based on current cancel implementation)
    get_response_after = client.get(f"/public/v1/work-items/{work_item_id}")
    assert get_response_after.status_code == 200
    item_after_cancel = get_response_after.json()
    assert item_after_cancel["work_item_id"] == work_item_id
    assert item_after_cancel["status"] == WorkItemStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_nonexistent_work_item(client: TestClient):
    """Test canceling a work item that doesn't exist."""
    # This would yield a bad request given the invalid uuid
    response = client.post("/public/v1/work-items/nonexistent-id/cancel")

    assert response.status_code == 400
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "bad_request"
    assert "invalid uuid" in detail["error"]["message"].lower()

    # We don't check existence, so this would yield 200
    response = client.post("/public/v1/work-items/00000000-0000-0000-0000-000000000000/cancel")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_full_workflow(client: TestClient, seed_agents: list[Agent]):
    """Test a complete workflow: create -> describe -> list -> cancel."""
    # 1. Create
    create_payload = {
        "agent_id": seed_agents[1].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Full workflow test"}]}],
        "payload": {"workflow": "complete"},
    }

    create_response = client.post("/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # 2. Describe
    describe_response = client.get(f"/public/v1/work-items/{work_item_id}")
    assert describe_response.status_code == 200
    described_item = describe_response.json()
    assert described_item["work_item_id"] == work_item_id
    assert described_item["agent_id"] == seed_agents[1].agent_id

    # 3. List (should contain our item)
    list_response = client.get("/public/v1/work-items/")
    assert list_response.status_code == 200
    items = list_response.json()
    item_ids = [item["work_item_id"] for item in items]
    assert work_item_id in item_ids

    # Check that items returned from list endpoint have empty messages
    for listed_work_item in items:
        assert listed_work_item["messages"] == []

    # 4. Cancel
    cancel_response = client.post(f"/public/v1/work-items/{work_item_id}/cancel")
    assert cancel_response.status_code == 200

    # 5. Verify cancellation
    final_describe_response = client.get(f"/public/v1/work-items/{work_item_id}")
    assert final_describe_response.status_code == 200
    final_describe_item = final_describe_response.json()
    assert final_describe_item["work_item_id"] == work_item_id
    assert final_describe_item["status"] == WorkItemStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_upload_file_to_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test uploading a file to a work item."""
    # Create a test file
    test_content = b"This is test file content for work item"
    test_file = ("test_file.txt", BytesIO(test_content), "text/plain")

    # Upload file without work_item_id (should create new work item)
    response = client.post("/public/v1/work-items/upload-file", files={"file": test_file})

    assert response.status_code == 200
    data = response.json()
    assert "work_item_id" in data
    work_item_id = data["work_item_id"]

    # Verify work item was created in PRECREATED state
    get_response = client.get(f"/public/v1/work-items/{work_item_id}")
    assert get_response.status_code == 200
    work_item = get_response.json()
    assert work_item["status"] == WorkItemStatus.PRECREATED.value
    assert work_item["agent_id"] is None  # No agent assigned yet


@pytest.mark.asyncio
async def test_upload_file_to_existing_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test uploading a file to an existing work item."""
    # First create a work item in PRECREATED state
    test_file1 = ("file1.txt", BytesIO(b"First file content"), "text/plain")

    response = client.post("/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Upload another file to the same work item
    test_file2 = ("file2.txt", BytesIO(b"Second file content"), "text/plain")

    response = client.post(
        f"/public/v1/work-items/upload-file?work_item_id={work_item_id}", files={"file": test_file2}
    )

    assert response.status_code == 200
    assert response.json()["work_item_id"] == work_item_id


@pytest.mark.asyncio
async def test_upload_duplicate_file_name_to_work_item(
    client: TestClient, seed_agents: list[Agent]
):
    """Test uploading a file with duplicate name to work item should fail."""
    # Create work item with first file
    test_file1 = ("duplicate.txt", BytesIO(b"First content"), "text/plain")

    response = client.post("/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to upload file with same name
    test_file2 = ("duplicate.txt", BytesIO(b"Second content"), "text/plain")

    response = client.post(
        f"/public/v1/work-items/upload-file?work_item_id={work_item_id}", files={"file": test_file2}
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_file_to_nonexistent_work_item(client: TestClient, seed_agents: list[Agent]):
    """Test uploading a file to a non-existent work item should fail."""
    test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")
    fake_work_item_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/public/v1/work-items/upload-file?work_item_id={fake_work_item_id}",
        files={"file": test_file},
    )

    assert response.status_code == 404
    assert "A work item with the given ID was not found" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_file_to_non_precreated_work_item(
    client: TestClient, seed_agents: list[Agent]
):
    """Test uploading a file to a work item not in PRECREATED state should fail."""
    # Create a work item with agent (will be in PENDING state)
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [{"role": "user", "content": [{"kind": "text", "text": "Test message"}]}],
        "payload": {},
    }

    response = client.post("/public/v1/work-items/", json=payload)
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Try to upload file to PENDING work item
    test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")

    response = client.post(
        f"/public/v1/work-items/upload-file?work_item_id={work_item_id}", files={"file": test_file}
    )

    assert response.status_code == 400
    assert "not in precreated state" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_work_item_with_files_workflow(client: TestClient, seed_agents: list[Agent]):
    """Test complete workflow: upload files -> create work item -> verify files copied to thread."""
    # 1. Upload files to create work item
    test_file1 = ("document.txt", BytesIO(b"Important document content"), "text/plain")
    test_file2 = ("data.csv", BytesIO(b"col1,col2\nval1,val2"), "text/csv")

    # Upload first file
    response = client.post("/public/v1/work-items/upload-file", files={"file": test_file1})
    assert response.status_code == 200
    work_item_id = response.json()["work_item_id"]

    # Upload second file to same work item
    response = client.post(
        f"/public/v1/work-items/upload-file?work_item_id={work_item_id}", files={"file": test_file2}
    )
    assert response.status_code == 200

    # 2. Convert work item to PENDING by adding agent and messages
    payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Process these files"}]}
        ],
        "payload": {"task": "file_processing"},
        "work_item_id": work_item_id,
    }

    response = client.post("/public/v1/work-items/", json=payload)
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
async def test_create_describe_and_list_work_item_with_callback(
    client: TestClient, seed_agents: list[Agent]
):
    """Test creating a work item with callback, then describing and listing to
    verify callbacks are included."""
    # Create a work item with a callback
    create_payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Test message with callback"}]}
        ],
        "payload": {"test_key": "test_value"},
        "callbacks": [
            {
                "url": "https://example.com/webhook",
                "signature_secret": "secret123",
                "on_status": "NEEDS_REVIEW",
            }
        ],
    }

    create_response = client.post("/public/v1/work-items/", json=create_payload)
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
    describe_response = client.get(f"/public/v1/work-items/{work_item_id}")
    assert describe_response.status_code == 200
    described_work_item = describe_response.json()
    assert len(described_work_item["callbacks"]) == 1
    described_callback = described_work_item["callbacks"][0]
    assert described_callback["url"] == "https://example.com/webhook"
    assert described_callback["signature_secret"] == "secret123"
    assert described_callback["on_status"] == "NEEDS_REVIEW"

    # Test list endpoint includes callbacks
    list_response = client.get("/public/v1/work-items/")
    assert list_response.status_code == 200
    work_items = list_response.json()

    # Find our work item in the list
    target_work_item = None
    for item in work_items:
        if item["work_item_id"] == work_item_id:
            target_work_item = item
            break

    assert target_work_item is not None
    assert len(target_work_item["callbacks"]) == 1
    listed_callback = target_work_item["callbacks"][0]
    assert listed_callback["url"] == "https://example.com/webhook"
    assert listed_callback["signature_secret"] == "secret123"
    assert listed_callback["on_status"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_create_work_item_with_multiple_callbacks(
    client: TestClient, seed_agents: list[Agent]
):
    """Test creating a work item with multiple callbacks for different statuses."""
    create_payload = {
        "agent_id": seed_agents[1].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Multiple callbacks test"}]}
        ],
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

    response = client.post("/public/v1/work-items/", json=create_payload)
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
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Test invalid callback"}]}
        ],
        "payload": {},
        "callbacks": [callback_config],
    }

    response = client.post("/public/v1/work-items/", json=payload)
    assert response.status_code == expected_status.value
    error_detail = response.json()
    assert "error" in error_detail


@pytest.mark.asyncio
async def test_cannot_create_multiple_callbacks_for_same_status(
    client: TestClient, seed_agents: list[Agent]
):
    """Test creating a work item with multiple callbacks for the same status."""
    # Create a work item with a callback
    create_payload = {
        "agent_id": seed_agents[0].agent_id,
        "messages": [
            {"role": "user", "content": [{"kind": "text", "text": "Test message with callback"}]}
        ],
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

    create_response = client.post("/public/v1/work-items/", json=create_payload)
    assert create_response.status_code == HTTPStatus.BAD_REQUEST.value
