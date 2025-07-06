import asyncio
import time

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.work_items import WorkItemStatus

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def fast_worker_settings_env():
    """Ensure the background worker runs frequently during the test session."""
    import os

    # Trigger the worker every second so we don't wait 30 s (default)
    os.environ.setdefault("WORKITEMS_WORKER_INTERVAL", "1")
    # Keep the timeout short-ish (60 s instead of 20 min)
    os.environ.setdefault("WORKITEMS_WORK_ITEM_TIMEOUT", "60")


@pytest.fixture
def agent_id(base_url_agent_server_with_work_items: str, openai_api_key: str):
    """Create a temporary agent for the tests and clean it up afterwards."""
    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
        )
        yield agent_id
        # Agents are removed in the context manager's __exit__


async def _wait_until(cond, interval: float = 1.0, timeout: float = 30):
    """Utility coroutine to wait until *cond* returns True (async) or timeout expires."""
    start = time.time()
    while True:
        if asyncio.iscoroutinefunction(cond):
            if await cond():
                return
        elif cond():
            return
        if time.time() - start > timeout:
            raise TimeoutError("Condition not met before timeout")
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_full_workflow_integration(base_url_agent_server_with_work_items: str, agent_id: str):
    """E2E: create --> describe --> list --> cancel on work-items endpoints."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/v2/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Create
        payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "Integration test workflow"}],
                }
            ],
            "payload": {"workflow": "integration_test"},
        }

        resp = await client.post("/", json=payload)
        assert resp.status_code == 200, resp.text
        item = resp.json()
        work_item_id = item["work_item_id"]

        assert item["agent_id"] == agent_id
        assert item["thread_id"] is None  # Thread not yet created
        assert item["status"] == WorkItemStatus.PENDING.value
        assert item["messages"][0]["content"][0]["text"] == "Integration test workflow"
        assert item["payload"]["workflow"] == "integration_test"
        assert "created_at" in item

        # 2. Describe (default results = false)
        desc_resp = await client.get(f"/{work_item_id}")
        assert desc_resp.status_code == 200
        desc_item = desc_resp.json()
        assert desc_item["work_item_id"] == work_item_id
        assert len(desc_item["messages"]) == 0

        # With results=true
        desc_results = await client.get(f"/{work_item_id}?results=true")
        assert desc_results.status_code == 200
        desc_item = desc_results.json()
        assert len(desc_item["messages"]) == 1
        assert desc_item["messages"][0]["content"][0]["text"] == "Integration test workflow"

        # 3. List
        list_resp = await client.get("/")
        assert list_resp.status_code == 200
        ids = [wi["work_item_id"] for wi in list_resp.json()]
        assert work_item_id in ids

        # 4. Cancel
        cancel_resp = await client.post(f"/{work_item_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "ok"

        # 5. Verify cancellation
        final_resp = await client.get(f"/{work_item_id}")
        assert final_resp.status_code == 200
        final_status = final_resp.json()["status"]
        assert final_status in {
            WorkItemStatus.CANCELLED.value,
            # Can this race w/ worker? Should we check for COMPLETED too?
        }


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_process_single_work_item(base_url_agent_server_with_work_items: str, agent_id: str):
    """Create a work item and wait until background worker marks it COMPLETED."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/v2/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        resp = await client.post(
            "/",
            json={
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"kind": "text", "text": "Please echo back this text"}],
                    }
                ],
                "payload": {"workflow": "integration_test"},
            },
        )
        assert resp.status_code == 200
        work_item_id = resp.json()["work_item_id"]

        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            return WorkItemStatus(r.json()["status"]) == WorkItemStatus.COMPLETED

        await _wait_until(_is_completed, interval=1.0, timeout=60)

        r = await client.get(f"/{work_item_id}")
        assert WorkItemStatus(r.json()["status"]) == WorkItemStatus.COMPLETED


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_batch_processing(base_url_agent_server_with_work_items: str, agent_id: str):
    """Create multiple work items and ensure they all complete."""

    num_items = 5
    work_items_url = f"{base_url_agent_server_with_work_items}/api/v2/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        work_item_ids = []
        for i in range(num_items):
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"kind": "text", "text": f"Batch message {i}"}],
                        }
                    ],
                    "payload": {},
                },
            )
            assert resp.status_code == 200
            work_item_ids.append(resp.json()["work_item_id"])

        assert len(work_item_ids) == num_items

        async def _all_completed():
            for wid in work_item_ids:
                r = await client.get(f"/{wid}")
                assert r.status_code == 200
                if WorkItemStatus(r.json()["status"]) != WorkItemStatus.COMPLETED:
                    return False
            return True

        await _wait_until(_all_completed, interval=1.0, timeout=90)

        # Final verification
        for wid in work_item_ids:
            r = await client.get(f"/{wid}")
            assert WorkItemStatus(r.json()["status"]) == WorkItemStatus.COMPLETED


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_batch_processing_with_errors(
    base_url_agent_server_with_work_items: str,
    agent_id: str,
):
    """Create a batch, cancel a subset, and verify mixed statuses (COMPLETED & CANCELLED)."""

    total_items = 5
    work_items_url = f"{base_url_agent_server_with_work_items}/api/v2/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        work_item_ids: list[str] = []

        # Step 1: create work-items
        for i in range(total_items):
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"kind": "text", "text": f"Cancellation test {i}"}],
                        }
                    ],
                    "payload": {},
                },
            )
            assert resp.status_code == 200
            work_item_ids.append(resp.json()["work_item_id"])

        # Step 2: Immediately cancel first two items
        to_cancel = work_item_ids[:2]
        for wid in to_cancel:
            r = await client.post(f"/{wid}/cancel")
            assert r.status_code == 200

        # Step 3: wait for remaining items to complete
        async def _desired_states():
            for wid in work_item_ids:
                r = await client.get(f"/{wid}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                if wid in to_cancel:
                    if status != WorkItemStatus.CANCELLED:
                        return False
                elif status != WorkItemStatus.COMPLETED:
                    return False
            return True

        await _wait_until(_desired_states, interval=1.0, timeout=90)

        # Final assertions
        for wid in work_item_ids:
            r = await client.get(f"/{wid}")
            status = WorkItemStatus(r.json()["status"])
            if wid in to_cancel:
                assert status == WorkItemStatus.CANCELLED
            else:
                assert status == WorkItemStatus.COMPLETED
