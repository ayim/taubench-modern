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

    response = client.post("/v2/work-items/", json=payload)

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

    response = client.post("/v2/work-items/", json=payload)

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

    create_response = client.post("/v2/work-items/", json=create_payload)
    work_item_id = create_response.json()["work_item_id"]

    # Get work item with results=true (return messages)
    response = client.get(f"/v2/work-items/{work_item_id}?results=true")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 1  # Messages should be included
    assert data["messages"][0]["content"][0]["kind"] == "text"
    assert data["messages"][0]["content"][0]["text"] == "Test message with results"

    # Get work item with results=false (default, no messages)
    response = client.get(f"/v2/work-items/{work_item_id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 0  # Messages should not be included


@pytest.mark.asyncio
async def test_describe_nonexistent_work_item(client: TestClient):
    """Test describing a work item that doesn't exist."""
    response = client.get("/v2/work-items/00000000-0000-0000-0000-000000000000")

    # Valid uuid, so not found
    assert response.status_code == 404
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "not_found"
    assert "not found" in detail["error"]["message"].lower()

    response = client.get("/v2/work-items/invalid-uuid")

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
    work_items = []
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

        create_response = client.post("/v2/work-items/", json=create_payload)
        assert create_response.status_code == 200
        work_items.append(create_response.json())

    # List work items
    response = client.get("/v2/work-items/")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 3

    # Check that our created items are in the list
    work_item_ids = {item["work_item_id"] for item in data}
    for work_item in work_items:
        assert work_item["work_item_id"] in work_item_ids


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

        create_response = client.post("/v2/work-items/", json=create_payload)
        assert create_response.status_code == 200

    # List with limit=2
    response = client.get("/v2/work-items/?limit=2")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2


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

    create_response = client.post("/v2/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # Verify the item exists before canceling
    get_response = client.get(f"/v2/work-items/{work_item_id}")
    assert get_response.status_code == 200

    # Cancel the work item
    cancel_response = client.post(f"/v2/work-items/{work_item_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "ok"

    # Verify the item is deleted (based on current cancel implementation)
    get_response_after = client.get(f"/v2/work-items/{work_item_id}")
    assert get_response_after.status_code == 200
    item_after_cancel = get_response_after.json()
    assert item_after_cancel["work_item_id"] == work_item_id
    assert item_after_cancel["status"] == WorkItemStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_nonexistent_work_item(client: TestClient):
    """Test canceling a work item that doesn't exist."""
    # This would yield a bad request given the invalid uuid
    response = client.post("/v2/work-items/nonexistent-id/cancel")

    assert response.status_code == 400
    detail = response.json()
    assert "error" in detail
    assert "code" in detail["error"]
    assert detail["error"]["code"] == "bad_request"
    assert "invalid uuid" in detail["error"]["message"].lower()

    # We don't check existence, so this would yield 200
    response = client.post("/v2/work-items/00000000-0000-0000-0000-000000000000/cancel")
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

    create_response = client.post("/v2/work-items/", json=create_payload)
    assert create_response.status_code == 200
    work_item = create_response.json()
    work_item_id = work_item["work_item_id"]

    # 2. Describe
    describe_response = client.get(f"/v2/work-items/{work_item_id}")
    assert describe_response.status_code == 200
    described_item = describe_response.json()
    assert described_item["work_item_id"] == work_item_id
    assert described_item["agent_id"] == seed_agents[1].agent_id

    # 3. List (should contain our item)
    list_response = client.get("/v2/work-items/")
    assert list_response.status_code == 200
    items = list_response.json()
    item_ids = [item["work_item_id"] for item in items]
    assert work_item_id in item_ids

    # 4. Cancel
    cancel_response = client.post(f"/v2/work-items/{work_item_id}/cancel")
    assert cancel_response.status_code == 200

    # 5. Verify cancellation
    final_describe_response = client.get(f"/v2/work-items/{work_item_id}")
    assert final_describe_response.status_code == 200
    final_describe_item = final_describe_response.json()
    assert final_describe_item["work_item_id"] == work_item_id
    assert final_describe_item["status"] == WorkItemStatus.CANCELLED.value
