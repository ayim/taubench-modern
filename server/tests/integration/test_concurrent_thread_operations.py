import asyncio
import random
import uuid
from typing import Any

import httpx
import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient


@pytest.mark.integration
async def test_concurrent_sqlite_operations(base_url_agent_server):
    """
    Test concurrent thread operations to ensure no commit-in-progress errors.

    This test performs 300 random operations (create, update, list) concurrently
    and verifies that all operations complete with HTTP 200 responses.
    """
    # Ensure server is up
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url_agent_server}/api/v2/ok", timeout=10)
        response.raise_for_status()

    # Create agent using client
    client = AgentServerClient(base_url_agent_server)
    agent_id = client.create_agent_and_return_agent_id(
        name=f"concurrent-test-{str(uuid.uuid4())[:8]}",
        runbook="# Objective\nYou are a helpful assistant for concurrent testing.",
        platform_configs=[{"kind": "openai", "openai_api_key": "test-key-for-concurrent-test"}],
    )
    print(f"Created agent: {agent_id}")

    # Create a base thread that we'll repeatedly update to trigger ON CONFLICT paths
    async with httpx.AsyncClient() as client:
        base_thread_response = await client.post(
            f"{base_url_agent_server}/api/v2/threads/",
            json={
                "agent_id": agent_id,
                "name": "base-thread-for-updates",
                "messages": [
                    {"role": "user", "content": [{"type": "input_text", "text": "initial message"}]}
                ],
            },
            timeout=15,
        )
        base_thread_response.raise_for_status()
    base_thread_id = base_thread_response.json()["thread_id"]
    print(f"Created base thread for updates: {base_thread_id}")

    # Create some work
    work = await _create_work(base_url_agent_server, agent_id, base_thread_id)

    # Execute operations concurrently
    async def execute_operation(operation_type: str, args: tuple[Any, ...]) -> tuple[str, int, str]:
        """Execute a single operation and return (type, status_code, response_text)."""
        try:
            match operation_type:
                case "update":
                    return await _do_update(*args)
                case "create":
                    return await _do_create(*args)
                case "list":
                    return await _do_list(*args)
                case _:
                    return operation_type, 500, f"Unknown operation type: {operation_type}"
        except Exception as e:
            return operation_type, 500, f"Exception: {e}"

    # Run all operations concurrently with limited concurrency to avoid overwhelming the server
    semaphore = asyncio.Semaphore(50)  # Limit concurrent operations

    async def bounded_operation(op_type: str, args: tuple[Any, ...]) -> tuple[str, int, str]:
        async with semaphore:
            return await execute_operation(op_type, args)

    print("Starting concurrent operations...")
    results = await asyncio.gather(
        *(bounded_operation(op_type, args) for op_type, args in work), return_exceptions=True
    )

    await _analyze_results(len(work), results)


async def _analyze_results(
    num_operations: int, results: list[tuple[str, int, str] | BaseException]
):
    # Analyze results
    successful_operations = 0
    failed_operations = 0
    errors_by_type: dict[str, list[tuple[int, str]]] = {"update": [], "create": [], "list": []}

    for result in results:
        if isinstance(result, BaseException):
            failed_operations += 1
            print(f"Exception in operation: {result}")
            continue

        op_type, status_code, response_text = result

        if status_code == 200:
            successful_operations += 1
        else:
            failed_operations += 1
            errors_by_type[op_type].append((status_code, response_text[:200]))

    print(f"Results: {successful_operations} successful, {failed_operations} failed")

    # Report any errors
    for op_type, errors in errors_by_type.items():
        if errors:
            print(f"{op_type.upper()} errors ({len(errors)}):")
            for i, (status, text) in enumerate(errors[:5]):  # Show first 5 errors
                print(f"  [{i}] Status {status}: {text!r}")

    # The test passes if all operations completed with HTTP 200
    assert successful_operations == num_operations, (
        f"Expected all {num_operations} operations to succeed with HTTP 200, "
        f"but only {successful_operations} succeeded. "
        f"Failed operations: {failed_operations}"
    )


async def _create_work(
    base_url: str, agent_id: str, base_thread_id: str
) -> list[tuple[str, tuple[Any, ...]]]:
    n_updates = 100
    n_creates = 100
    n_lists = 100

    work: list[tuple[str, tuple[Any, ...]]] = []

    # Add update operations (all target the same thread to trigger conflicts)
    for i in range(n_updates):
        work.append(("update", (base_url, agent_id, base_thread_id, i)))

    # Add create operations (create new threads)
    for i in range(n_creates):
        work.append(("create", (base_url, agent_id, i)))

    # Add list operations
    for i in range(n_lists):
        work.append(("list", (base_url, agent_id, i)))

    # Shuffle to create random interleavings
    random.shuffle(work)

    return work


async def _do_update(base_url: str, agent_id: str, thread_id: str, i: int) -> tuple[str, int, str]:
    """Update an existing thread (triggers ON CONFLICT path in storage)."""
    url = f"{base_url}/api/v2/threads/{thread_id}"
    payload = {
        "agent_id": agent_id,
        "name": f"updated-thread-{i}",
        "messages": [{"role": "user", "content": [{"type": "input_text", "text": f"update-{i}"}]}],
    }

    # Add small random jitter to create interleavings
    await asyncio.sleep(random.uniform(0, 0.01))

    async with httpx.AsyncClient() as client:
        response = await client.put(url, json=payload, timeout=15)
        return "update", response.status_code, response.text


async def _do_create(base_url: str, agent_id: str, i: int) -> tuple[str, int, str]:
    """Create a new thread."""
    url = f"{base_url}/api/v2/threads/"
    payload = {
        "agent_id": agent_id,
        "name": f"new-thread-{i}",
        "messages": [{"role": "user", "content": [{"type": "input_text", "text": f"create-{i}"}]}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=15)
        return "create", response.status_code, response.text


async def _do_list(base_url: str, agent_id: str, i: int) -> tuple[str, int, str]:
    """List threads for the agent."""
    url = f"{base_url}/api/v2/threads/?agent_id={agent_id}"

    # Add small random jitter to mix with writes
    await asyncio.sleep(random.uniform(0, 0.01))

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15)
        return "list", response.status_code, response.text
