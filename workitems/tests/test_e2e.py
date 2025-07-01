import logging
import time

import pytest
from httpx import AsyncClient

from agent_platform.workitems.models import WorkItemStatus

logger = logging.getLogger(__name__)


async def wait_until(condition, *args, interval=1.0, timeout=10):
    start = time.time()
    while not await condition(*args) and time.time() - start < timeout:
        time.sleep(interval)


@pytest.mark.integration
class TestWorkItemsE2E:
    """E2E tests for work item CRUD operations. These talk to openai -- add tests sparingly."""

    @pytest.mark.asyncio
    async def test_full_workflow_integration(
        self,
        require_docker,
        agent_server_url: str,
        agent_id: str,
        request,
    ):
        """Test a complete workflow against running server: create -> describe -> list -> cancel."""
        work_items_server_url = agent_server_url + "/api/work-items/v1/work-items"
        async with AsyncClient(base_url=work_items_server_url) as client:
            # 1. Create
            create_payload = {
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"kind": "text", "text": "Integration test workflow"}],
                    }
                ],
                "payload": {"workflow": "integration_test"},
            }

            create_response = await client.post("/", json=create_payload)
            assert create_response.status_code == 200, (
                f"Failed to create work item: {create_response.text}"
            )
            work_item = create_response.json()
            work_item_id = work_item["work_item_id"]

            assert work_item["agent_id"] == agent_id
            assert work_item["thread_id"], "did not get a thread id"
            assert work_item["status"] == WorkItemStatus.PENDING.value
            assert len(work_item["messages"]) == 1
            assert work_item["messages"][0]["role"] == "user"
            assert work_item["messages"][0]["content"][0]["text"] == "Integration test workflow"
            assert work_item["payload"]["workflow"] == "integration_test"
            assert "created_at" in work_item

            # 2. Describe
            describe_response = await client.get(f"/{work_item_id}")
            assert describe_response.status_code == 200
            described_item = describe_response.json()
            assert described_item["work_item_id"] == work_item_id
            assert described_item["agent_id"] == agent_id
            assert len(described_item["messages"]) == 0  # Default is results=false

            # Test with results=true
            describe_with_results_response = await client.get(f"/{work_item_id}?results=true")
            assert describe_with_results_response.status_code == 200
            described_with_results = describe_with_results_response.json()
            assert len(described_with_results["messages"]) == 1
            assert (
                described_with_results["messages"][0]["content"][0]["text"]
                == "Integration test workflow"
            )

            # 3. List (should contain our item)
            list_response = await client.get("/")
            assert list_response.status_code == 200
            items = list_response.json()
            assert isinstance(items, list)
            item_ids = [item["work_item_id"] for item in items]
            assert work_item_id in item_ids

            # 4. Cancel
            cancel_response = await client.post(f"/{work_item_id}/cancel")
            assert cancel_response.status_code == 200
            assert cancel_response.json()["status"] == "ok"

            # 5. Verify cancellation with a describe
            final_describe_response = await client.get(f"/{work_item_id}")
            assert final_describe_response.status_code == 200
            final_describe_item = final_describe_response.json()
            assert final_describe_item["work_item_id"] == work_item_id
            assert final_describe_item["status"] == WorkItemStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_process_work_item(
        self,
        require_docker,
        agent_server_url: str,
        agent_id: str,
        request,
    ):
        """Test a complete workflow against running server: create -> describe -> list -> cancel."""
        work_items_server_url = agent_server_url + "/api/work-items/v1/work-items"
        async with AsyncClient(base_url=work_items_server_url) as client:
            # 1. Create a work item
            create_payload = {
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"kind": "text", "text": "Integration test workflow"}],
                    }
                ],
                "payload": {"workflow": "integration_test"},
            }

            create_response = await client.post("/", json=create_payload)
            assert create_response.status_code == 200, (
                f"Failed to create work item: {create_response.json()}"
            )
            work_item = create_response.json()
            assert work_item["status"] == WorkItemStatus.PENDING.value
            work_item_id = work_item["work_item_id"]

            # Make sure the work item gets marked as COMPLETED
            async def verify_status(work_item_id: str, desired: WorkItemStatus) -> bool:
                response = await client.get(f"/{work_item_id}")
                assert response.status_code == 200
                logger.info(f"Work item {work_item_id} status: {response.json()['status']}")
                return WorkItemStatus(response.json()["status"]) == desired

            await wait_until(verify_status, work_item_id, WorkItemStatus.COMPLETED, timeout=10)

            # describe it once more to make sure it's actually completed (vs. timing out)
            response = await client.get(f"/{work_item_id}")
            assert response.status_code == 200
            assert WorkItemStatus(response.json()["status"]) == WorkItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_batch_processing(
        self,
        require_docker,
        agent_server_url: str,
        agent_id: str,
        request,
    ):
        num_work_items = 5  # fewer than the batch size
        """Test a complete workflow against running server: create -> describe -> list -> cancel."""
        work_items_server_url = agent_server_url + "/api/work-items/v1/work-items"
        async with AsyncClient(base_url=work_items_server_url) as client:
            work_item_ids = []
            # Create multiple work item
            for i in range(num_work_items):
                create_payload = {
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"kind": "text", "text": f"Integration test workflow {i}"}],
                        }
                    ],
                    "payload": {},
                }

                create_response = await client.post("/", json=create_payload)
                assert create_response.status_code == 200, (
                    f"Failed to create work item: {create_response.json()}"
                )
                work_item = create_response.json()
                assert work_item["status"] == WorkItemStatus.PENDING.value
                work_item_ids.append(work_item["work_item_id"])

            assert len(work_item_ids) == num_work_items

            # Make sure the work item gets marked as COMPLETED
            async def verify_status(work_item_ids: list[str], desired: WorkItemStatus) -> bool:
                for work_item_id in work_item_ids:
                    response = await client.get(f"/{work_item_id}")
                    assert response.status_code == 200
                    logger.info(f"Work item {work_item_id} status: {response.json()['status']}")
                    if WorkItemStatus(response.json()["status"]) != desired:
                        return False
                return True

            # Wait for all work items to be completed
            await wait_until(verify_status, work_item_ids, WorkItemStatus.COMPLETED, timeout=10)

            # make sure they are all processed
            for work_item_id in work_item_ids:
                response = await client.get(f"/{work_item_id}")
                assert response.status_code == 200
                assert WorkItemStatus(response.json()["status"]) == WorkItemStatus.COMPLETED, (
                    f"Work item {work_item_id} is not completed"
                )

    @pytest.mark.asyncio
    async def test_batch_processing_with_errors(
        self,
        require_docker,
        agent_server_url: str,
        agent_id: str,
    ):
        num_work_items = 5  # fewer than the batch size
        """Test a complete workflow against running server: create -> describe -> list -> cancel."""
        work_items_server_url = agent_server_url + "/api/work-items/v1/work-items"
        async with AsyncClient(base_url=work_items_server_url) as client:
            work_item_ids = []
            # Create multiple work item
            for i in range(num_work_items):
                create_payload = {
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"kind": "text", "text": f"Integration test workflow {i}"}],
                        }
                    ],
                    "payload": {},
                }

                create_response = await client.post("/", json=create_payload)
                assert create_response.status_code == 200, (
                    f"Failed to create work item: {create_response.json()}"
                )
                work_item = create_response.json()
                assert work_item["status"] == WorkItemStatus.PENDING.value
                work_item_ids.append(work_item["work_item_id"])

            assert len(work_item_ids) == num_work_items

            # Make sure the work item gets marked as COMPLETED
            async def verify_status(work_item_ids: list[str], desired: WorkItemStatus) -> bool:
                for work_item_id in work_item_ids:
                    response = await client.get(f"/{work_item_id}")
                    assert response.status_code == 200
                    logger.info(f"Work item {work_item_id} status: {response.json()['status']}")
                    if WorkItemStatus(response.json()["status"]) != desired:
                        return False
                return True

            # Wait for all work items to be completed
            await wait_until(verify_status, work_item_ids, WorkItemStatus.COMPLETED, timeout=10)

            # make sure they are all processed
            for work_item_id in work_item_ids:
                response = await client.get(f"/{work_item_id}")
                assert response.status_code == 200
                assert WorkItemStatus(response.json()["status"]) == WorkItemStatus.COMPLETED, (
                    f"Work item {work_item_id} is not completed"
                )
