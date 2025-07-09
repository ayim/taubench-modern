import asyncio
import time
from io import BytesIO

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

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_batch_processing(base_url_agent_server_with_work_items: str, agent_id: str):
    """Create multiple work items and ensure they all complete."""

    num_items = 5
    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
            for wid in work_item_ids:
                r = await client.get(f"/{wid}")
                assert r.status_code == 200
                status = WorkItemStatus(r.json()["status"])
                if status != WorkItemStatus.COMPLETED:
                    return False
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
async def test_batch_processing_with_errors(
    base_url_agent_server_with_work_items: str,
    agent_id: str,
):
    """Create a batch, cancel a subset, and verify mixed statuses (COMPLETED & CANCELLED)."""

    total_items = 5
    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_process_single_work_item__failed_success_validation(
    base_url_agent_server_with_work_items: str, openai_api_key: str, agent_id: str
):
    """Create a work item and wait until background worker marks it NEEDS_REVIEW."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_process_single_work_item__with_calculation_tool(
    base_url_agent_server_with_work_items: str,
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

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
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

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_validation_completed(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test end-to-end work item validation with a simple task that should be marked as COMPLETED.

    This test verifies that the work item validation logic correctly processes
    simple, straightforward tasks and marks them as successfully completed.
    """

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create an agent with a simple successful task
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. Always respond with exactly what the user asks for. "
                "Be concise and complete your tasks fully."
            ),
        )

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_validation_needs_review(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test end-to-end work item validation with a task that should result in NEEDS_REVIEW.

    This test verifies that the work item validation logic correctly identifies
    incomplete or uncertain responses that require human review.
    """

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create an agent that will struggle with complex analysis
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you encounter complex requests "
                "that require external data or specialized knowledge you don't have, "
                "you should express uncertainty and request human assistance."
            ),
        )

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_validation_behavior_with_simple_tasks(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test work item validation behavior across multiple task types.

    This test verifies that the validation logic processes different types
    of tasks and produces reasonable classifications.
    """

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create an agent for simple tasks
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook="You are a helpful assistant. Complete tasks as requested.",
        )

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_validation_needs_review_missing_tools(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test work item validation with a task requiring tools the agent doesn't have.

    This test verifies that when an agent is asked to perform actions it cannot
    complete due to missing tools or capabilities, it gets marked as NEEDS_REVIEW.
    """

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create an agent without any action packages/tools
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you are asked to perform actions "
                "that require tools or capabilities you don't have, you should clearly "
                "state that you cannot complete the task and request human assistance."
            ),
        )

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_validation_needs_review_incomplete_task(
    base_url_agent_server_with_work_items: str, openai_api_key: str
):
    """Test work item validation with an incomplete or ambiguous task.

    This test verifies that when an agent receives contradictory or incomplete
    instructions, it requests clarification and gets marked as NEEDS_REVIEW.
    """

    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        # Create an agent that should ask for clarification on ambiguous tasks
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[{"kind": "openai", "openai_api_key": openai_api_key}],
            runbook=(
                "You are a helpful assistant. When you receive incomplete or "
                "contradictory instructions, you should ask for clarification "
                "rather than making assumptions. Request human input when needed."
            ),
        )

        work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_file_upload_workflow(
    base_url_agent_server_with_work_items: str, agent_id: str
):
    """Test complete workflow: upload files → create work item → verify files copied to thread."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_file_upload_duplicate_handling(
    base_url_agent_server_with_work_items: str, agent_id: str
):
    """Test that duplicate file names are properly rejected."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_file_upload_state_validation(
    base_url_agent_server_with_work_items: str, agent_id: str
):
    """Test that files can only be uploaded to PRECREATED work items."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
        assert "not in precreated state" in error_msg.lower()


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_file_upload_nonexistent_work_item(
    base_url_agent_server_with_work_items: str,
):
    """Test uploading to non-existent work item returns proper error."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"
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
async def test_work_item_multiple_file_types_processing(
    base_url_agent_server_with_work_items: str, agent_id: str
):
    """Test processing work item with multiple file types."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"

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
async def test_work_item_batch_file_processing(
    base_url_agent_server_with_work_items: str, agent_id: str
):
    """Test batch processing of multiple work items with files."""

    work_items_url = f"{base_url_agent_server_with_work_items}/api/public/v1/work-items"
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
