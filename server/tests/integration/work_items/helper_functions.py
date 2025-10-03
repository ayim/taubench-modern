import asyncio
import time
from typing import Any

import pytest

from agent_platform.core.work_items import WorkItemStatus


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


async def _create_work_items_for_tasks(client, agent_id, tasks):
    """Helper function to create work items for a list of tasks."""
    results = []
    for task in tasks:
        resp = await client.post(
            "/",
            json={
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"kind": "text", "text": task}],
                    }
                ],
                "payload": {"workflow": "integration_test"},
            },
        )
        assert resp.status_code == 200
        work_item_id = resp.json()["work_item_id"]
        results.append((task, work_item_id))
    return results


async def _wait_for_all_work_items_completion(client, all_work_items):
    """Helper function to wait for all work items to complete."""

    async def _all_completed():
        for _, work_item_id in all_work_items:
            r = await client.get(f"/{work_item_id}")
            if r.status_code != 200:
                return False
            status = WorkItemStatus(r.json()["status"])
            if status not in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]:
                return False
        return True

    await _wait_until(_all_completed, interval=2.0, timeout=120)


async def _count_work_item_statuses(client, simple_results, problematic_results):
    """Helper function to count work item statuses."""
    completed_count = 0
    needs_review_count = 0

    for _task, work_item_id in simple_results:
        r = await client.get(f"/{work_item_id}")
        status = WorkItemStatus(r.json()["status"])
        if status == WorkItemStatus.COMPLETED:
            completed_count += 1

    for _task, work_item_id in problematic_results:
        r = await client.get(f"/{work_item_id}")
        status = WorkItemStatus(r.json()["status"])
        if status == WorkItemStatus.NEEDS_REVIEW:
            needs_review_count += 1

    return completed_count, needs_review_count


def make_text_message(text: str) -> list[dict[str, Any]]:
    """Create a standard text message for work item requests."""
    return [
        {
            "role": "user",
            "content": [{"kind": "text", "text": text}],
        }
    ]


def assert_work_item_url(
    body: dict[str, Any], agent_id: str, work_item_id: str, thread_id: str
) -> None:
    """Assert that the work item URL has the expected format."""
    expected_url_suffix = f"{agent_id}/{work_item_id}/{thread_id}"
    assert body["work_item_url"].endswith(expected_url_suffix)
    # With default test settings, should start with "http://localhost:8000/"
    assert body["work_item_url"].startswith("https://localhost:8000/tenants/123/worker/")


def _fail_on_needs_review(status: WorkItemStatus):
    """Utility function to fail on NEEDS_REVIEW status."""
    if status == WorkItemStatus.NEEDS_REVIEW:
        raise pytest.fail("Test failed because of NEEDS_REVIEW status")  # type: ignore
