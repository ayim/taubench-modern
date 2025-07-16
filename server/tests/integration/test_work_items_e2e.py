import asyncio
import json
import threading
import time
import unittest.mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from httpx import AsyncClient

from agent_platform.core.work_items import WorkItemStatus
from agent_platform.core.work_items.work_item import WorkItem, WorkItemCallback

# Import cloud server fixture for file upload tests
from server.tests.files.test_api_endpoints_cloud import cloud_server  # noqa: F401

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
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_full_workflow_integration(base_url_fixture: str, request, agent_id: str):
    """E2E: create --> describe --> list --> cancel on work-items endpoints."""

    url = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url}/api/public/v1/work-items"
    print(f"work_items_url: {work_items_url}")

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
        listed_items = list_resp.json()
        ids = [wi["work_item_id"] for wi in listed_items]
        assert work_item_id in ids

        # Verify that items returned from list endpoint have empty messages
        for listed_item in listed_items:
            assert listed_item["messages"] == []

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
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_process_single_work_item(base_url_fixture: str, request, agent_id: str):
    """Create a work item and wait until background worker marks it COMPLETED."""

    url = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url}/api/public/v1/work-items"

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
            status = WorkItemStatus(r.json()["status"])
            return status == WorkItemStatus.COMPLETED

        await _wait_until(_is_completed, interval=1.0, timeout=60)

        r = await client.get(f"/{work_item_id}")
        status = WorkItemStatus(r.json()["status"])
        assert status == WorkItemStatus.COMPLETED


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_batch_processing(base_url_fixture: str, request, agent_id: str):
    """Create multiple work items and ensure they all complete."""

    url = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url}/api/public/v1/work-items"
    num_items = 5

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
                            "content": [
                                {
                                    "kind": "text",
                                    "text": f"Echo back this text: Batch message {i}",
                                }
                            ],
                        }
                    ],
                    "payload": {},
                },
            )
            assert resp.status_code == 200
            work_item_ids.append(resp.json()["work_item_id"])

        assert len(work_item_ids) == num_items

        async def _all_completed():
            statuses = []
            for wid in work_item_ids:
                r = await client.get(f"/{wid}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                statuses.append((wid, status))
                if status != WorkItemStatus.COMPLETED:
                    print(f"[batch status check] wid={wid} status={status}")
                    return False
            print(f"[batch status check] All statuses: {statuses}")
            return True

        await _wait_until(_all_completed, interval=1.0, timeout=90)

        # Final verification - both COMPLETED and NEEDS_REVIEW are valid outcomes
        for wid in work_item_ids:
            r = await client.get(f"/{wid}")
            status = WorkItemStatus(r.json()["status"])
            assert status == WorkItemStatus.COMPLETED


@pytest.mark.integration
@pytest.mark.skip(reason="Skipping this test until cancelled work items are handled correctly")
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_batch_processing_with_errors(base_url_fixture: str, request, agent_id: str):
    """Create a batch, cancel a subset, and verify mixed statuses (COMPLETED & CANCELLED)."""

    url = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url}/api/public/v1/work-items"
    total_items = 5

    async with AsyncClient(base_url=work_items_url) as client:
        work_item_ids: list[str] = []

        # Step 1: create work-items
        for _ in range(total_items):
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            # Create a simple question that can easily pass the validation check
                            "content": [{"kind": "text", "text": "What is 2+2?"}],
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
                elif status not in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]:
                    return False
            return True

        await _wait_until(_desired_states, interval=1.0, timeout=90)

        # Final assertions - both COMPLETED and NEEDS_REVIEW are valid outcomes
        for wid in work_item_ids:
            r = await client.get(f"/{wid}")
            status = WorkItemStatus(r.json()["status"])
            if wid in to_cancel:
                assert status == WorkItemStatus.CANCELLED
            else:
                assert status in [WorkItemStatus.COMPLETED]


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_process_single_work_item__failed_success_validation(
    base_url_fixture: str, request, openai_api_key: str, agent_id: str
):
    """Create a work item and wait until background worker marks it NEEDS_REVIEW."""
    url = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        resp = await client.post(
            "/",
            json={
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        # This is a bogus computation that should cause the LLM to error out
                        "content": [{"kind": "text", "text": "foo + 942382"}],
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
            return WorkItemStatus(r.json()["status"]) == WorkItemStatus.NEEDS_REVIEW

        await _wait_until(_is_completed, interval=1.0, timeout=60)

        r = await client.get(f"/{work_item_id}")
        assert WorkItemStatus(r.json()["status"]) == WorkItemStatus.NEEDS_REVIEW


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_process_single_work_item__with_calculation_tool(  # noqa: PLR0913
    base_url_fixture: str,
    request,
    openai_api_key: str,
    action_server_process,
    logs_dir,
    resources_dir,
):
    """
    Create a work item with calculation task and verify
    it gets completed using the calculate tool.
    """
    from agent_platform.orchestrator.agent_server_client import (
        ActionPackage,
        AgentServerClient,
        SecretKey,
    )

    # Start the action server with the simple action package that includes the calculate function
    cwd = resources_dir / "simple_action_package"
    api_key = "test"
    action_server_process.start(
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,
        additional_args=["--api-key", api_key],
        logs_dir=logs_dir,
    )
    url = f"http://{action_server_process.host}:{action_server_process.port}"

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            action_packages=[
                ActionPackage(
                    name="CalculationPackage",
                    organization="TestOrg",
                    version="1.0.0",
                    url=url,
                    api_key=SecretKey(value=api_key),
                    whitelist="",
                    allowed_actions=["calculate"],  # Only allow the calculate action
                )
            ],
            runbook="You are a helpful assistant that solves math problems. "
            "Always use the calculate tool for mathematical operations.",
        )

        async with AsyncClient(base_url=work_items_url) as client:
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"kind": "text", "text": "What is 15 * 8 + 7?"}],
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
                status = WorkItemStatus(r.json()["status"])
                return status == WorkItemStatus.COMPLETED

            await _wait_until(_is_completed, interval=1.0, timeout=60)

            r = await client.get(f"/{work_item_id}?results=true")  # Include results to get messages
            assert r.status_code == 200
            final_status = WorkItemStatus(r.json()["status"])

            # The work item should be completed
            assert final_status == WorkItemStatus.COMPLETED

            # Verify the calculation was performed correctly
            work_item_data = r.json()
            messages = work_item_data.get("messages", [])

            # Look for the calculation result (15 * 8 + 7 = 127) or tool usage
            found_calculation = False
            found_tool_usage = False

            for message in messages:
                if "content" in message:
                    for content in message["content"]:
                        text = content.get("text", "")
                        kind = content.get("kind", "")

                        # Check for the result in text content
                        if kind == "text" and "127" in text:
                            found_calculation = True
                            break

                        # Check for tool usage (calculate function being called)
                        if kind == "tool_usage" and "calculate" in text.lower():
                            found_tool_usage = True
                            if "127" in text:
                                found_calculation = True
                                break

                    if found_calculation:
                        break

            assert found_calculation or found_tool_usage, (
                f"Expected calculation result (127) or tool usage not found. Messages: {messages}"
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_work_item_validation_completed(base_url_fixture: str, request, openai_api_key: str):
    """Test end-to-end work item validation with a simple task that should be marked as COMPLETED.

    This test verifies that the work item validation logic correctly processes
    simple, straightforward tasks and marks them as successfully completed.
    """
    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        # Create an agent with a simple successful task
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. Always respond with exactly what the user asks for. "
                "Be concise and complete your tasks fully."
            ),
        )

        async with AsyncClient(base_url=work_items_url) as client:
            # Create a work item with a simple, clearly completable task
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "kind": "text",
                                    "text": "Say hello",
                                }
                            ],
                        }
                    ],
                    "payload": {"workflow": "integration_test"},
                },
            )
            assert resp.status_code == 200
            work_item_id = resp.json()["work_item_id"]

            # Wait for completion
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            await _wait_until(_is_final_status, interval=1.0, timeout=60)

            # Get the final result
            r = await client.get(f"/{work_item_id}?results=true")
            final_status = WorkItemStatus(r.json()["status"])

            # This simple task should be marked as COMPLETED by the validation logic
            assert final_status == WorkItemStatus.COMPLETED, (
                f"Expected COMPLETED but got {final_status}"
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_work_item_validation_needs_review(
    base_url_fixture: str, request, openai_api_key: str
):
    """Test end-to-end work item validation with a task that should result in NEEDS_REVIEW.

    This test verifies that the work item validation logic correctly identifies
    incomplete or uncertain responses that require human review.
    """
    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        # Create an agent that will struggle with complex analysis
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you encounter complex requests "
                "that require external data or specialized knowledge you don't have, "
                "you should express uncertainty and request human assistance."
            ),
        )

        async with AsyncClient(base_url=work_items_url) as client:
            # Create a work item that requires complex analysis the agent cannot complete
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "kind": "text",
                                    "text": (
                                        "Analyze the Q3 2024 financial performance of our company "
                                        "against competitors "
                                        "and provide specific recommendations for"
                                        "improving our market position. "
                                        "I need exact revenue figures, "
                                        "profit margins, and market share data."
                                    ),
                                }
                            ],
                        }
                    ],
                    "payload": {"workflow": "integration_test"},
                },
            )
            assert resp.status_code == 200
            work_item_id = resp.json()["work_item_id"]

            # Wait for completion
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            await _wait_until(_is_final_status, interval=1.0, timeout=60)

            # Get the final result
            r = await client.get(f"/{work_item_id}?results=true")
            final_status = WorkItemStatus(r.json()["status"])

            # The agent should express uncertainty about providing exact financial data
            # and request human intervention, leading to NEEDS_REVIEW
            assert final_status == WorkItemStatus.NEEDS_REVIEW, (
                f"Expected NEEDS_REVIEW but got {final_status}. "
                f"Agent should have expressed uncertainty about providing exact financial data."
            )


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


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_work_item_validation_behavior_with_simple_tasks(
    base_url_fixture: str, request, openai_api_key: str
):
    """Test work item validation behavior across multiple task types.

    This test verifies that the validation logic processes different types
    of tasks and produces reasonable classifications.
    """

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        # Create an agent for simple tasks
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook="You are a helpful assistant. Complete tasks as requested.",
        )

        # Test cases that should generally be COMPLETED
        simple_tasks = ["List three colors", "Count from 1 to 5", "Say 'task complete'"]

        # Test cases that should generally be NEEDS_REVIEW
        problematic_tasks = [
            "Delete the most important files from the server",
            "Execute this SQL: DROP TABLE users;",
        ]

        async with AsyncClient(base_url=work_items_url) as client:
            # Create work items for all tasks
            simple_results = await _create_work_items_for_tasks(client, agent_id, simple_tasks)
            problematic_results = await _create_work_items_for_tasks(
                client, agent_id, problematic_tasks
            )

            # Wait for all tasks to complete
            all_work_items = simple_results + problematic_results
            await _wait_for_all_work_items_completion(client, all_work_items)

            # Count the results
            completed_count, needs_review_count = await _count_work_item_statuses(
                client, simple_results, problematic_results
            )

            # Verify that the validation system is working
            total_tasks = len(simple_tasks) + len(problematic_tasks)
            classified_tasks = completed_count + needs_review_count

            # At least 60% of tasks should be properly classified
            assert classified_tasks >= int(total_tasks * 0.6), (
                f"Expected at least 60% of tasks to be classified correctly, "
                f"got {classified_tasks}/{total_tasks}"
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_work_item_validation_needs_review_missing_tools(
    base_url_fixture: str, request, openai_api_key: str
):
    """Test work item validation with a task requiring tools the agent doesn't have.

    This test verifies that when an agent is asked to perform actions it cannot
    complete due to missing tools or capabilities, it gets marked as NEEDS_REVIEW.
    """
    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        # Create an agent without any action packages/tools
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you are asked to perform actions "
                "that require tools or capabilities you don't have, you should clearly "
                "state that you cannot complete the task and request human assistance."
            ),
        )

        async with AsyncClient(base_url=work_items_url) as client:
            # Create a work item that requires sending an email (which requires tools)
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "kind": "text",
                                    "text": (
                                        "Send an email to john@company.com with the subject "
                                        "'Project Update' and include our latest quarterly results."
                                    ),
                                }
                            ],
                        }
                    ],
                    "payload": {"workflow": "integration_test"},
                },
            )
            assert resp.status_code == 200
            work_item_id = resp.json()["work_item_id"]

            # Wait for completion
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            await _wait_until(_is_final_status, interval=1.0, timeout=60)

            # Get the final result
            r = await client.get(f"/{work_item_id}?results=true")
            final_status = WorkItemStatus(r.json()["status"])

            # The agent should recognize it cannot send emails and request human help
            assert final_status == WorkItemStatus.NEEDS_REVIEW, (
                f"Expected NEEDS_REVIEW but got {final_status}. "
                f"Agent should have recognized it cannot send emails without tools."
            )


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
    ],
)
async def test_work_item_validation_needs_review_incomplete_task(
    base_url_fixture: str, request, openai_api_key: str
):
    """Test work item validation with an incomplete or ambiguous task.

    This test verifies that when an agent receives contradictory or incomplete
    instructions, it requests clarification and gets marked as NEEDS_REVIEW.
    """
    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    with AgentServerClient(url_agent_server) as agent_client:
        # Create an agent that should ask for clarification on ambiguous tasks
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you receive incomplete or "
                "contradictory instructions, you should ask for clarification "
                "rather than making assumptions. Request human input when needed."
            ),
        )

        async with AsyncClient(base_url=work_items_url) as client:
            # Create a work item with contradictory/incomplete instructions
            resp = await client.post(
                "/",
                json={
                    "agent_id": agent_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "kind": "text",
                                    "text": (
                                        "Process all the customer data from last month "
                                        "but make sure not to process any customer data. "
                                        "Also, generate a report "
                                        "but don't create any documents."
                                    ),
                                }
                            ],
                        }
                    ],
                    "payload": {"workflow": "integration_test"},
                },
            )
            assert resp.status_code == 200
            work_item_id = resp.json()["work_item_id"]

            # Wait for completion
            async def _is_final_status():
                r = await client.get(f"/{work_item_id}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

            await _wait_until(_is_final_status, interval=1.0, timeout=60)

            # Get the final result
            r = await client.get(f"/{work_item_id}?results=true")
            final_status = WorkItemStatus(r.json()["status"])

            # The agent should recognize the contradictory instructions and ask for clarification
            assert final_status == WorkItemStatus.NEEDS_REVIEW, (
                f"Expected NEEDS_REVIEW but got {final_status}. "
                f"Agent should have asked for clarification on contradictory instructions."
            )


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_file_upload_workflow(base_url_fixture: str, request, agent_id: str):
    """Test complete workflow: upload files → create work item → verify files copied to thread."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Upload first file (creates work item in PRECREATED state)
        test_file1 = (
            "document.txt",
            BytesIO(b"Important document content for agent"),
            "text/plain",
        )

        upload_resp = await client.post("/upload-file", files={"file": test_file1})
        assert upload_resp.status_code == 200
        work_item_id = upload_resp.json()["work_item_id"]

        # Verify work item is in PRECREATED state
        get_resp = await client.get(f"/{work_item_id}")
        assert get_resp.status_code == 200
        work_item = get_resp.json()
        assert work_item["status"] == WorkItemStatus.PRECREATED.value
        assert work_item["agent_id"] is None

        # 2. Upload second file to same work item
        test_file2 = ("data.csv", BytesIO(b"name,value\ntest,123"), "text/csv")

        upload_resp2 = await client.post(
            f"/upload-file?work_item_id={work_item_id}", files={"file": test_file2}
        )
        assert upload_resp2.status_code == 200
        assert upload_resp2.json()["work_item_id"] == work_item_id

        # 3. Convert work item to PENDING by adding agent and messages
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "kind": "text",
                            "text": "List the uploaded files",
                        }
                    ],
                }
            ],
            "payload": {"task": "file_analysis"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200
        work_item = create_resp.json()

        # Verify work item is now PENDING with agent
        assert work_item["status"] == WorkItemStatus.PENDING.value
        assert work_item["agent_id"] == agent_id
        assert work_item["work_item_id"] == work_item_id

        # 4. Wait for background worker to process the work item
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            return WorkItemStatus(r.json()["status"]) == WorkItemStatus.COMPLETED

        await _wait_until(_is_completed, interval=1.0, timeout=90)

        # 5. Verify final state
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        assert WorkItemStatus(final_work_item["status"]) == WorkItemStatus.COMPLETED
        assert final_work_item["thread_id"] is not None  # Thread should be created

        # Verify messages include file upload notifications
        messages = final_work_item["messages"]
        assert len(messages) >= 3  # User message + 2 file upload messages

        # Check for file upload messages
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 2  # One for each file


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_file_upload_duplicate_handling(
    base_url_fixture: str, request, agent_id: str
):
    """Test that duplicate file names are properly rejected."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # Upload first file
        test_file1 = ("duplicate.txt", BytesIO(b"First content"), "text/plain")

        upload_resp = await client.post("/upload-file", files={"file": test_file1})
        assert upload_resp.status_code == 200
        work_item_id = upload_resp.json()["work_item_id"]

        # Try to upload file with same name - should fail
        test_file2 = ("duplicate.txt", BytesIO(b"Second content"), "text/plain")

        duplicate_resp = await client.post(
            f"/upload-file?work_item_id={work_item_id}", files={"file": test_file2}
        )
        assert duplicate_resp.status_code == 400
        error_msg = duplicate_resp.json()["error"]["message"]
        assert "already exists" in error_msg
        assert "duplicate.txt" in error_msg


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_file_upload_state_validation(
    base_url_fixture: str, request, agent_id: str
):
    """Test that files can only be uploaded to PRECREATED work items."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # Create work item directly in PENDING state (with agent)
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "Test message"}],
                }
            ],
            "payload": {},
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200
        work_item_id = create_resp.json()["work_item_id"]

        # Verify work item is in PENDING state
        get_resp = await client.get(f"/{work_item_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == WorkItemStatus.PENDING.value

        # Try to upload file to PENDING work item - should fail
        test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")

        upload_resp = await client.post(
            f"/upload-file?work_item_id={work_item_id}", files={"file": test_file}
        )
        assert upload_resp.status_code == 400
        error_msg = upload_resp.json()["error"]["message"]
        assert "Files can only be attached to work-items in the PRECREATED state." in error_msg


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_file_upload_nonexistent_work_item(base_url_fixture: str, request):
    """Test uploading to non-existent work item returns proper error."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"
    fake_work_item_id = "00000000-0000-0000-0000-000000000000"

    async with AsyncClient(base_url=work_items_url) as client:
        test_file = ("test.txt", BytesIO(b"Test content"), "text/plain")

        upload_resp = await client.post(
            f"/upload-file?work_item_id={fake_work_item_id}", files={"file": test_file}
        )
        assert upload_resp.status_code == 404
        error_msg = upload_resp.json()["error"]["message"]
        assert "A work item with the given ID was not found" in error_msg


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_multiple_file_types_processing(
    base_url_fixture: str, request, agent_id: str
):
    """Test processing work item with multiple file types."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # Upload different file types
        files_to_upload = [
            ("readme.txt", BytesIO(b"This is a text file with instructions"), "text/plain"),
            ("data.json", BytesIO(b'{"key": "value", "number": 42}'), "application/json"),
            (
                "config.xml",
                BytesIO(b'<?xml version="1.0"?><config><setting>value</setting></config>'),
                "text/xml",
            ),
        ]

        work_item_id = None

        for i, (filename, content, mime_type) in enumerate(files_to_upload):
            file_tuple = (filename, content, mime_type)

            if i == 0:
                # First file creates the work item
                upload_resp = await client.post("/upload-file", files={"file": file_tuple})
                assert upload_resp.status_code == 200
                work_item_id = upload_resp.json()["work_item_id"]
            else:
                # Subsequent files are added to existing work item
                upload_resp = await client.post(
                    f"/upload-file?work_item_id={work_item_id}", files={"file": file_tuple}
                )
                assert upload_resp.status_code == 200
                assert upload_resp.json()["work_item_id"] == work_item_id

        # Convert to PENDING and process
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "List the uploaded files"}],
                }
            ],
            "payload": {"task": "file_listing"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200

        # Wait for completion
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            return WorkItemStatus(r.json()["status"]) == WorkItemStatus.COMPLETED

        await _wait_until(_is_completed, interval=1.0, timeout=90)

        # Verify all files were processed
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        assert WorkItemStatus(final_work_item["status"]) == WorkItemStatus.COMPLETED

        # Check that all 3 files generated upload messages
        messages = final_work_item["messages"]
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 3  # One for each file type


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_batch_file_processing(base_url_fixture: str, request, agent_id: str):
    """Test batch processing of multiple work items with files."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"
    num_work_items = 3

    async with AsyncClient(base_url=work_items_url) as client:
        work_item_ids = []

        # Create multiple work items with files
        for i in range(num_work_items):
            # Upload file
            test_file = (
                f"batch_file_{i}.txt",
                BytesIO(f"Batch content {i}".encode()),
                "text/plain",
            )

            upload_resp = await client.post("/upload-file", files={"file": test_file})
            assert upload_resp.status_code == 200
            work_item_id = upload_resp.json()["work_item_id"]

            # Convert to PENDING
            create_payload = {
                "agent_id": agent_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"kind": "text", "text": "I need a simple list of the uploaded files."}
                        ],
                    }
                ],
                "payload": {"batch_index": i},
                "work_item_id": work_item_id,
            }

            create_resp = await client.post("/", json=create_payload)
            assert create_resp.status_code == 200
            work_item_ids.append(work_item_id)

        # Wait for all work items to complete
        async def _all_completed():
            for wid in work_item_ids:
                r = await client.get(f"/{wid}")
                assert r.status_code == 200
                if WorkItemStatus(r.json()["status"]) != WorkItemStatus.COMPLETED:
                    return False
            return True

        await _wait_until(_all_completed, interval=1.0, timeout=120)

        # Verify all work items completed successfully
        for wid in work_item_ids:
            final_resp = await client.get(f"/{wid}?results=true")
            assert final_resp.status_code == 200
            final_work_item = final_resp.json()

            assert WorkItemStatus(final_work_item["status"]) == WorkItemStatus.COMPLETED
            assert final_work_item["thread_id"] is not None

            # Verify file upload message exists
            messages = final_work_item["messages"]
            file_upload_messages = [
                msg
                for msg in messages
                if msg["role"] == "user"
                and any(
                    content.get("text", "").startswith("Uploaded")
                    for content in msg.get("content", [])
                )
            ]
            assert len(file_upload_messages) == 1  # One file per work item


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems",
        "base_url_agent_server_postgres_workitems",
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_file_ownership(base_url_fixture: str, request, agent_id: str):  # noqa: PLR0915
    """
    Verify complete file ownership workflow from upload
    through processing, including system user ownership and proper file associations.

    This test verifies:
    - Files are owned by system user (not uploading user)
    - associate_work_item_file works correctly during background processing
    - Multiple files are handled properly
    - Complete workflow: PRECREATED → PENDING → COMPLETED
    """
    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Upload multiple files to test both system user ownership and associate_work_item_file
        files_to_upload = [
            ("file1.txt", BytesIO(b"First file content"), "text/plain"),
            ("file2.txt", BytesIO(b"Second file content"), "text/plain"),
        ]

        work_item_id = None
        for i, (filename, content, mime_type) in enumerate(files_to_upload):
            file_tuple = (filename, content, mime_type)

            if i == 0:
                upload_resp = await client.post("/upload-file", files={"file": file_tuple})
                assert upload_resp.status_code == 200
                work_item_id = str(upload_resp.json()["work_item_id"])
            else:
                upload_resp = await client.post(
                    f"/upload-file?work_item_id={work_item_id}", files={"file": file_tuple}
                )
                assert upload_resp.status_code == 200

        # Ensure work_item_id is not None
        assert work_item_id is not None

        # 2. Verify initial state (PRECREATED)
        get_resp = await client.get(f"/{work_item_id}")
        assert get_resp.status_code == 200
        work_item = get_resp.json()
        assert work_item["status"] == WorkItemStatus.PRECREATED.value

        # 3. Convert to PENDING state
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "Process both uploaded files"}],
                }
            ],
            "payload": {"test": "e2e_validation"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200

        # 4. Verify state changed to PENDING
        pending_resp = await client.get(f"/{work_item_id}")
        assert pending_resp.status_code == 200
        pending_work_item = pending_resp.json()
        assert pending_work_item["status"] == WorkItemStatus.PENDING.value
        assert pending_work_item["agent_id"] == agent_id

        # 5. Wait for background worker processing
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            status = WorkItemStatus(r.json()["status"])
            # Wait for NEEDS_REVIEW status - the agent is asked to "process files" but has no
            # file processing tools available, so the validator correctly identifies that
            # the task cannot be completed and marks it for human review
            return status == WorkItemStatus.NEEDS_REVIEW

        await _wait_until(_is_completed, interval=1.0, timeout=60)

        # 6. Verify final state and file associations
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        # Assert NEEDS_REVIEW status - this is expected because the agent cannot actually
        # process files without file processing tools, so the validator marks it for review
        final_status = WorkItemStatus(final_work_item["status"])
        assert final_status == WorkItemStatus.NEEDS_REVIEW
        assert final_work_item["thread_id"] is not None

        # 7. Verify file upload messages were added (indicates associate_work_item_file worked)
        messages = final_work_item["messages"]
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 2  # Two files uploaded

        # 8. Verify both files are referenced in upload messages
        uploaded_files = []
        for upload_message in file_upload_messages:
            upload_text = upload_message["content"][0]["text"]
            if "Uploaded [file1.txt]" in upload_text:
                uploaded_files.append("file1.txt")
            elif "Uploaded [file2.txt]" in upload_text:
                uploaded_files.append("file2.txt")

        assert len(uploaded_files) == 2
        assert "file1.txt" in uploaded_files
        assert "file2.txt" in uploaded_files

        # 9. Verify workflow completed successfully with both files processed
        # NEEDS_REVIEW status indicates the background worker processed successfully,
        # but the agent could not complete the file processing task due to lack of tools.
        # This is the expected behavior for our test scenario:
        # - Files were owned by system user (upload worked)
        # - associate_work_item_file worked (files copied to thread)
        # - Background worker processed successfully (reached final status)
        assert final_status == WorkItemStatus.NEEDS_REVIEW


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_two_stage_file_upload_workflow(  # noqa: PLR0915
    base_url_fixture: str,
    request,
    agent_id: str,
    cloud_server,  # noqa: F811
):
    """Test complete two-stage file upload workflow:
    request -> cloud upload -> confirm -> process."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Request remote upload (creates work item in PRECREATED state)
        upload_request_resp = await client.post(
            "/upload-file", data={"file": "important-document.pdf"}
        )
        assert upload_request_resp.status_code == 200
        upload_data = upload_request_resp.json()

        work_item_id = upload_data["work_item_id"]
        upload_url = upload_data["upload_url"]
        form_data = upload_data["upload_form_data"]
        file_id = upload_data["file_id"]
        file_ref = upload_data["file_ref"]

        # Verify work item is in PRECREATED state
        get_resp = await client.get(f"/{work_item_id}")
        assert get_resp.status_code == 200
        work_item = get_resp.json()
        assert work_item["status"] == WorkItemStatus.PRECREATED.value
        assert work_item["agent_id"] is None

        # 2. Upload file to cloud storage using presigned URL
        import httpx

        test_file_content = b"This is a test PDF document content"

        async with httpx.AsyncClient() as http_client:
            # Upload to cloud storage
            upload_resp = await http_client.post(
                upload_url,
                data=form_data,
                files={"file": ("important-document.pdf", test_file_content, "application/pdf")},
            )
            assert upload_resp.status_code == 200

        # 3. Confirm the upload
        confirm_payload = {"file_ref": file_ref, "file_id": file_id}

        confirm_resp = await client.post(f"/{work_item_id}/confirm-file", json=confirm_payload)
        assert confirm_resp.status_code == 200
        confirm_data = confirm_resp.json()
        assert confirm_data["work_item_id"] == work_item_id

        # 4. Convert work item to PENDING by adding agent and messages
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "kind": "text",
                            "text": "Analyze the uploaded document",
                        }
                    ],
                }
            ],
            "payload": {"task": "document_analysis"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200
        work_item = create_resp.json()

        # Verify work item is now PENDING with agent
        assert work_item["status"] == WorkItemStatus.PENDING.value
        assert work_item["agent_id"] == agent_id
        assert work_item["work_item_id"] == work_item_id

        # 5. Wait for background worker to process the work item
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            status = WorkItemStatus(r.json()["status"])
            return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        await _wait_until(_is_completed, interval=1.0, timeout=90)

        # 6. Verify final state
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        final_status = WorkItemStatus(final_work_item["status"])
        assert final_status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]
        assert final_work_item["thread_id"] is not None  # Thread should be created

        # Verify messages include file upload notification
        messages = final_work_item["messages"]
        assert len(messages) >= 2  # User message + file upload message

        # Check for file upload message
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 1  # One file uploaded

        # Verify the file reference is in the upload message
        upload_text = file_upload_messages[0]["content"][0]["text"]
        assert file_ref in upload_text


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_two_stage_multiple_files_upload(
    base_url_fixture: str,
    request,
    agent_id: str,
    cloud_server,  # noqa: F811
):
    """Test two-stage upload workflow with multiple files."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        work_item_id = None
        uploaded_files = []

        # Test data for multiple files
        files_to_upload = [
            ("report.pdf", b"PDF report content", "application/pdf"),
            ("data.csv", b"CSV data content", "text/csv"),
            ("summary.txt", b"Summary text content", "text/plain"),
        ]

        for i, (filename, content, mime_type) in enumerate(files_to_upload):
            # 1. Request remote upload
            if i == 0:
                # First file creates the work item
                upload_request_resp = await client.post("/upload-file", data={"file": filename})
                assert upload_request_resp.status_code == 200
                upload_data = upload_request_resp.json()
                work_item_id = upload_data["work_item_id"]
            else:
                # Subsequent files are added to existing work item
                upload_request_resp = await client.post(
                    f"/upload-file?work_item_id={work_item_id}", data={"file": filename}
                )
                assert upload_request_resp.status_code == 200
                upload_data = upload_request_resp.json()
                assert upload_data["work_item_id"] == work_item_id

            # 2. Upload to cloud storage
            import httpx

            async with httpx.AsyncClient() as http_client:
                upload_resp = await http_client.post(
                    upload_data["upload_url"],
                    data=upload_data["upload_form_data"],
                    files={"file": (filename, content, mime_type)},
                )
                assert upload_resp.status_code == 200

            # 3. Confirm the upload
            confirm_payload = {
                "file_ref": upload_data["file_ref"],
                "file_id": upload_data["file_id"],
            }

            confirm_resp = await client.post(f"/{work_item_id}/confirm-file", json=confirm_payload)
            assert confirm_resp.status_code == 200

            uploaded_files.append(upload_data["file_ref"])

        # 4. Convert to PENDING and process
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "Process all uploaded files"}],
                }
            ],
            "payload": {"task": "multi_file_processing"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200

        # 5. Wait for completion
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            status = WorkItemStatus(r.json()["status"])
            return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        await _wait_until(_is_completed, interval=1.0, timeout=90)

        # 6. Verify all files were processed
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        final_status = WorkItemStatus(final_work_item["status"])
        assert final_status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        # Check that all 3 files generated upload messages
        messages = final_work_item["messages"]
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 3  # One for each file

        # Verify all files are referenced in upload messages
        for file_ref in uploaded_files:
            found = any(file_ref in msg["content"][0]["text"] for msg in file_upload_messages)
            assert found, f"File {file_ref} not found in upload messages"


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_two_stage_upload_error_handling(
    base_url_fixture: str,
    request,
    agent_id: str,
    cloud_server,  # noqa: F811
):
    """Test error handling in two-stage upload workflow."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Request remote upload
        upload_request_resp = await client.post("/upload-file", data={"file": "test-document.pdf"})
        assert upload_request_resp.status_code == 200
        upload_data = upload_request_resp.json()
        work_item_id = upload_data["work_item_id"]

        # 2. Test confirming upload without actually uploading to cloud
        confirm_payload = {"file_ref": upload_data["file_ref"], "file_id": upload_data["file_id"]}

        # This should not work as we don't have a file in cloud storage
        confirm_resp = await client.post(f"/{work_item_id}/confirm-file", json=confirm_payload)
        assert confirm_resp.status_code == 404
        assert "File not found in cloud storage" in confirm_resp.json()["error"]["message"]

        # 3. Test confirming with invalid file_id
        invalid_confirm_payload = {
            "file_ref": "invalid.pdf",
            "file_id": "00000000-0000-0000-0000-000000000001",
        }

        confirm_resp = await client.post(
            f"/{work_item_id}/confirm-file", json=invalid_confirm_payload
        )
        assert confirm_resp.status_code == 404
        assert "File not found in cloud storage" in confirm_resp.json()["error"]["message"]

        # 4. Test confirming for non-existent work item
        fake_work_item_id = "00000000-0000-0000-0000-000000000000"
        confirm_resp = await client.post(f"/{fake_work_item_id}/confirm-file", json=confirm_payload)
        assert confirm_resp.status_code == 404
        assert (
            "A work item with the given ID was not found" in confirm_resp.json()["error"]["message"]
        )

        # 5. Test requesting upload for non-existent work item
        upload_request_resp = await client.post(
            f"/upload-file?work_item_id={fake_work_item_id}", data={"file": "test.pdf"}
        )
        assert upload_request_resp.status_code == 404
        assert (
            "A work item with the given ID was not found"
            in upload_request_resp.json()["error"]["message"]
        )


@pytest.mark.integration
@pytest.mark.postgresql
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url_fixture",
    [
        "base_url_agent_server_sqlite_workitems_cloud",
        "base_url_agent_server_postgres_workitems_cloud",
    ],
)
async def test_work_item_mixed_upload_methods(
    base_url_fixture: str,
    request,
    agent_id: str,
    cloud_server,  # noqa: F811
):
    """Test mixing direct upload and two-stage upload methods."""

    url_agent_server = request.getfixturevalue(base_url_fixture)
    work_items_url = f"{url_agent_server}/api/public/v1/work-items"

    async with AsyncClient(base_url=work_items_url) as client:
        # 1. Start with direct upload (creates work item)
        direct_file = (
            "direct.txt",
            BytesIO(b"Direct upload content"),
            "text/plain",
        )

        direct_upload_resp = await client.post("/upload-file", files={"file": direct_file})
        assert direct_upload_resp.status_code == 200
        work_item_id = direct_upload_resp.json()["work_item_id"]

        # 2. Add file via two-stage upload to same work item
        upload_request_resp = await client.post(
            f"/upload-file?work_item_id={work_item_id}", data={"file": "two-stage.pdf"}
        )
        assert upload_request_resp.status_code == 200
        upload_data = upload_request_resp.json()
        assert upload_data["work_item_id"] == work_item_id

        # 3. Upload to cloud storage
        import httpx

        async with httpx.AsyncClient() as http_client:
            upload_resp = await http_client.post(
                upload_data["upload_url"],
                data=upload_data["upload_form_data"],
                files={"file": ("two-stage.pdf", b"Two-stage content", "application/pdf")},
            )
            assert upload_resp.status_code == 200

        # 4. Confirm the two-stage upload
        confirm_payload = {"file_ref": upload_data["file_ref"], "file_id": upload_data["file_id"]}

        confirm_resp = await client.post(f"/{work_item_id}/confirm-file", json=confirm_payload)
        assert confirm_resp.status_code == 200

        # 5. Convert to PENDING and process
        create_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"kind": "text", "text": "Process both uploaded files"}],
                }
            ],
            "payload": {"task": "mixed_upload_processing"},
            "work_item_id": work_item_id,
        }

        create_resp = await client.post("/", json=create_payload)
        assert create_resp.status_code == 200

        # 6. Wait for completion
        async def _is_completed():
            r = await client.get(f"/{work_item_id}")
            assert r.status_code == 200
            status = WorkItemStatus(r.json()["status"])
            return status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        await _wait_until(_is_completed, interval=1.0, timeout=90)

        # 7. Verify both files were processed
        final_resp = await client.get(f"/{work_item_id}?results=true")
        assert final_resp.status_code == 200
        final_work_item = final_resp.json()

        final_status = WorkItemStatus(final_work_item["status"])
        assert final_status in [WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW]

        # Check that both files generated upload messages
        messages = final_work_item["messages"]
        file_upload_messages = [
            msg
            for msg in messages
            if msg["role"] == "user"
            and any(
                content.get("text", "").startswith("Uploaded") for content in msg.get("content", [])
            )
        ]
        assert len(file_upload_messages) == 2  # Both direct and two-stage files

        # Verify both files are referenced
        upload_texts = [msg["content"][0]["text"] for msg in file_upload_messages]
        assert any("direct.txt" in text for text in upload_texts)
        assert any("two-stage.pdf" in text for text in upload_texts)


# ---------------------------------------------------------------------------
# Regression tests. See https://linear.app/sema4ai/issue/GPT-1080/
# ---------------------------------------------------------------------------


def _get_work_item_judge_test_files():
    """Get all JSON files from the work-item-threads-to-judge directory for parameterization."""

    # Get the directory path relative to this test file
    current_dir = Path(__file__).parent
    work_item_threads_dir = current_dir / "resources" / "work-item-threads-to-judge"

    if not work_item_threads_dir.exists():
        return []

    # Get all JSON files and create pytest parameters
    json_files = []
    for file_path in work_item_threads_dir.glob("*.json"):
        # Use the filename without extension as the test ID
        test_id = file_path.stem.replace("-", "_")
        json_files.append(pytest.param(file_path.name, id=test_id))

    return sorted(json_files, key=lambda x: x.values[0])  # Sort by filename


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize("resource_file", _get_work_item_judge_test_files())
async def test_work_item_judge_with_recorded_threads(
    base_url_agent_server_with_work_items: str,
    openai_api_key: str,
    resource_file: str,
    resources_dir: Path,
):
    """Test the work item judge using pre-recorded conversation threads.

    This test exercises the judge (_validate_success) with real model calls but uses
    pre-recorded conversation threads instead of running the full work item execution.
    This allows us to test the judge's decision-making without the complexity and
    non-determinism of full agent execution.

    Each JSON file contains an 'expected_status' field that defines what the judge
    should return for that conversation thread.
    """
    import json

    from agent_platform.server.work_items.background_worker import _validate_success

    # Load the recorded thread from JSON
    work_item_resources_dir = resources_dir / "work-item-threads-to-judge"
    with open(work_item_resources_dir / resource_file, encoding="utf-8") as fh:
        work_item_data = json.load(fh)

    # Extract expected status from the JSON file
    expected_status = WorkItemStatus(work_item_data.pop("expected_status"))

    # Convert to WorkItem object (without the expected_status field)
    work_item = WorkItem.model_validate(work_item_data)

    # Test the judge directly with a real model call
    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create a temporary agent for validation (the judge needs an agent_id)
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
        )
        work_item.agent_id = agent_id

        # Mock the storage service to provide what _validate_success needs
        from agent_platform.core.agent.agent import Agent
        from agent_platform.core.agent.agent_architecture import AgentArchitecture
        from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
        from agent_platform.core.runbook.runbook import Runbook
        from agent_platform.core.user import User
        from agent_platform.core.utils import SecretString
        from agent_platform.server.storage import StorageService

        # Create a mock user
        mock_user = User(user_id=work_item.user_id, sub="test_user")

        # Create a mock platform config
        mock_platform_config = OpenAIPlatformParameters(openai_api_key=SecretString(openai_api_key))

        # Create a mock agent
        mock_agent = Agent(
            name="Test Agent",
            description="Test agent for validation",
            user_id=work_item.user_id,
            runbook_structured=Runbook(raw_text="You are a helpful assistant", content=[]),
            version="1.0.0",
            platform_configs=[mock_platform_config],
            agent_architecture=AgentArchitecture(name="test_arch", version="1.0.0"),
        )

        # Create a mock storage service
        mock_storage = unittest.mock.AsyncMock()
        mock_storage.get_user_by_id.return_value = mock_user
        mock_storage.get_agent.return_value = mock_agent

        # Replace the storage service instance
        with unittest.mock.patch.object(StorageService, "get_instance", return_value=mock_storage):
            # Call the judge with real model call
            result_status = await _validate_success(work_item)

        # Assert the expected result
        assert result_status == expected_status, (
            f"Expected {expected_status} but got {result_status} for {resource_file}"
        )


# NOTE: Callback tests have been moved to test_work_items_callbacks.py
# This reduces duplication and improves maintainability.


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_callback_e2e_mocked_completion(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test end-to-end callback execution with mocked work item completion."""

    # Track received callback requests
    received_callbacks = []
    callback_event = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            received_callbacks.append(
                {"path": self.path, "headers": dict(self.headers), "body": json.loads(body)}
            )

            # Signal that we received a callback
            callback_event.set()

            # Send response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')

        def log_message(self, format, *args):  # noqa: A002
            # Suppress HTTP server logs during tests
            pass

    # Start callback server
    server = HTTPServer(("localhost", 0), CallbackHandler)
    server_port = server.server_address[1]
    callback_url = f"http://localhost:{server_port}/webhook"

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
            # Create agent with callback
            agent_id = agent_client.create_agent_and_return_agent_id(
                platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
                runbook="You are a helpful assistant.",
            )

            work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

            async with AsyncClient(base_url=work_items_url) as client:
                # Create work item with callback
                resp = await client.post(
                    "/",
                    json={
                        "agent_id": agent_id,
                        "messages": [
                            {
                                "role": "user",
                                "content": [{"kind": "text", "text": "Test message"}],
                            }
                        ],
                        "payload": {"workflow": "callback_test"},
                        "callbacks": [
                            {
                                "url": callback_url,
                                "on_status": "COMPLETED",
                            }
                        ],
                    },
                )
                assert resp.status_code == 200
                work_item_id = resp.json()["work_item_id"]

                # Wait for work item to be picked up by background worker
                await asyncio.sleep(2)

                # Manually trigger callback by directly calling the callback execution function
                # This simulates what would happen when a work item completes
                from agent_platform.server.work_items.callbacks import execute_callbacks

                # Create a mock work item for callback testing instead of accessing storage
                # This avoids the storage initialization issue in the test process
                work_item = WorkItem(
                    work_item_id=work_item_id,
                    user_id="test-user",
                    agent_id=agent_id,
                    thread_id="test-thread-123",  # Set a test thread ID
                    status=WorkItemStatus.COMPLETED,
                    callbacks=[
                        WorkItemCallback(
                            url=callback_url,
                            on_status=WorkItemStatus.COMPLETED,
                        )
                    ],
                )

                # Execute callbacks
                await execute_callbacks(work_item, WorkItemStatus.COMPLETED)

                # Wait for callback to be fired
                callback_received = callback_event.wait(timeout=5.0)
                assert callback_received, "Callback was not received within timeout"

                # Verify callback payload
                assert len(received_callbacks) == 1
                callback = received_callbacks[0]

                assert callback["path"] == "/webhook"
                assert callback["headers"]["Content-Type"] == "application/json"

                # Verify callback body
                body = callback["body"]
                assert body["work_item_id"] == work_item_id
                assert body["agent_id"] == agent_id
                assert body["status"] == "COMPLETED"
                assert body["thread_id"] == "test-thread-123"

                # Verify the work item URL format
                # With default test settings, should be "http://localhost:8000/{agent_id}/{work_item_id}"
                expected_url_suffix = f"{agent_id}/{work_item_id}"
                assert body["work_item_url"].endswith(expected_url_suffix)

                # Verify the URL starts with expected base
                assert body["work_item_url"].startswith("http://localhost:8000/")

    finally:
        server.shutdown()
        server_thread.join(timeout=1)
