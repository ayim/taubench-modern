import pytest
from httpx import AsyncClient

from agent_platform.workitems.models import (
    WorkItemStatus,
)


class TestWorkItemCRUD:
    """Test work item CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_work_item(self, require_docker, client: AsyncClient):
        """Test creating a work item."""
        payload = {
            "agent_id": "test-agent-1",
            "messages": [
                {"role": "user", "content": [{"kind": "text", "text": "Hello, test message"}]}
            ],
            "payload": {"test_key": "test_value"},
        }

        response = await client.post("/v1/work-items/", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "test-agent-1"
        assert data["thread_id"], "did not get a thread id"
        assert data["status"] == WorkItemStatus.PENDING.value
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"][0]["text"] == "Hello, test message"
        assert data["payload"]["test_key"] == "test_value"
        assert "work_item_id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_work_item_invalid_agent(self, require_docker, client: AsyncClient):
        """Test creating a work item with invalid agent ID."""
        payload = {
            "agent_id": "invalid-agent",
            "messages": [],
            "payload": {},
        }

        response = await client.post("/v1/work-items/", json=payload)

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_describe_work_item(self, require_docker, client: AsyncClient):
        """Test describing a work item with results included."""
        # First create a work item
        create_payload = {
            "agent_id": "test-agent-2",
            "messages": [
                {"role": "user", "content": [{"kind": "text", "text": "Test message with results"}]}
            ],
            "payload": {},
        }

        create_response = await client.post("/v1/work-items/", json=create_payload)
        work_item_id = create_response.json()["work_item_id"]

        # Get work item with results=true (return messages)
        response = await client.get(f"/v1/work-items/{work_item_id}?results=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1  # Messages should be included
        assert data["messages"][0]["content"][0]["kind"] == "text"
        assert data["messages"][0]["content"][0]["text"] == "Test message with results"

        # Get work item with results=false (default, no messages)
        response = await client.get(f"/v1/work-items/{work_item_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 0  # Messages should not be included

    @pytest.mark.asyncio
    async def test_describe_nonexistent_work_item(self, require_docker, client: AsyncClient):
        """Test describing a work item that doesn't exist."""
        response = await client.get("/v1/work-items/nonexistent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    @pytest.mark.asyncio
    async def test_list_work_items(self, require_docker, client: AsyncClient):
        """Test listing work items."""
        # Create multiple work items
        work_items = []
        for i in range(3):
            create_payload = {
                "agent_id": "test-agent-1",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"kind": "text", "text": f"List test message {i}"}],
                    }
                ],
                "payload": {"list_index": i},
            }

            create_response = await client.post("/v1/work-items/", json=create_payload)
            assert create_response.status_code == 200
            work_items.append(create_response.json())

        # List work items
        response = await client.get("/v1/work-items/")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 3

        # Check that our created items are in the list
        work_item_ids = {item["work_item_id"] for item in data}
        for work_item in work_items:
            assert work_item["work_item_id"] in work_item_ids

    @pytest.mark.asyncio
    async def test_list_work_items_with_limit(self, require_docker, client: AsyncClient):
        """Test listing work items with limit parameter."""
        # Create 5 work items
        for _ in range(5):
            create_payload = {
                "agent_id": "test-agent-1",
                "messages": [],
                "payload": {},
            }

            create_response = await client.post("/v1/work-items/", json=create_payload)
            assert create_response.status_code == 200

        # List with limit=2
        response = await client.get("/v1/work-items/?limit=2")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_cancel_work_item(self, require_docker, client: AsyncClient):
        """Test canceling a work item."""
        # First create a work item
        create_payload = {
            "agent_id": "test-agent-1",
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "This item will be canceled"}],
                }
            ],
            "payload": {"cancel_test": True},
        }

        create_response = await client.post("/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        work_item = create_response.json()
        work_item_id = work_item["work_item_id"]

        # Verify the item exists before canceling
        get_response = await client.get(f"/v1/work-items/{work_item_id}")
        assert get_response.status_code == 200

        # Cancel the work item
        cancel_response = await client.post(f"/v1/work-items/{work_item_id}/cancel")

        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "ok"

        # Verify the item is deleted (based on current cancel implementation)
        get_response_after = await client.get(f"/v1/work-items/{work_item_id}")
        assert get_response_after.status_code == 200
        item_after_cancel = get_response_after.json()
        assert item_after_cancel["work_item_id"] == work_item_id
        assert item_after_cancel["status"] == WorkItemStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_work_item(self, require_docker, client: AsyncClient):
        """Test canceling a work item that doesn't exist."""
        # This should still return 200 as the cancel method doesn't check existence
        response = await client.post("/v1/work-items/nonexistent-id/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_full_workflow(self, require_docker, client: AsyncClient):
        """Test a complete workflow: create -> describe -> list -> cancel."""
        # 1. Create
        create_payload = {
            "agent_id": "test-agent-2",
            "messages": [
                {"role": "user", "content": [{"kind": "text", "text": "Full workflow test"}]}
            ],
            "payload": {"workflow": "complete"},
        }

        create_response = await client.post("/v1/work-items/", json=create_payload)
        assert create_response.status_code == 200
        work_item = create_response.json()
        work_item_id = work_item["work_item_id"]

        # 2. Describe
        describe_response = await client.get(f"/v1/work-items/{work_item_id}")
        assert describe_response.status_code == 200
        described_item = describe_response.json()
        assert described_item["work_item_id"] == work_item_id
        assert described_item["agent_id"] == "test-agent-2"

        # 3. List (should contain our item)
        list_response = await client.get("/v1/work-items/")
        assert list_response.status_code == 200
        items = list_response.json()
        item_ids = [item["work_item_id"] for item in items]
        assert work_item_id in item_ids

        # 4. Cancel
        cancel_response = await client.post(f"/v1/work-items/{work_item_id}/cancel")
        assert cancel_response.status_code == 200

        # 5. Verify cancellation
        final_describe_response = await client.get(f"/v1/work-items/{work_item_id}")
        assert final_describe_response.status_code == 200
        final_describe_item = final_describe_response.json()
        assert final_describe_item["work_item_id"] == work_item_id
        assert final_describe_item["status"] == WorkItemStatus.CANCELLED.value
