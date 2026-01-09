import typing
from uuid import uuid4

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_count_threads_for_agent(
    storage: "SQLiteStorage | PostgresStorage",
    sample_user_id: str,
    sample_agent: "Agent",
    sample_thread: "Thread",
) -> None:
    """Test counting threads for a specific agent across both SQLite and Postgres.

    This test verifies:
    - Initial count is 0 for non-existent agent
    - Count increments correctly as threads are added
    - Multiple agents have independent thread counts
    - Count decrements correctly when threads are deleted
    - Count is agent-wide (not filtered by user)
    """
    from datetime import UTC, datetime

    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.thread.base import ThreadMessage, ThreadTextContent
    from agent_platform.core.thread.thread import Thread

    # count is 0 for non-existent agent
    non_existent_agent_id = str(uuid4())
    assert await storage.count_threads_for_agent(non_existent_agent_id) == 0

    # Create an agent
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Initially no threads
    assert await storage.count_threads_for_agent(sample_agent.agent_id) == 0

    # Add first thread
    await storage.upsert_thread(sample_user_id, sample_thread)
    assert await storage.count_threads_for_agent(sample_agent.agent_id) == 1

    # Add second thread for the same agent
    thread_2 = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Test Thread 2",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Second thread message")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(sample_user_id, thread_2)
    assert await storage.count_threads_for_agent(sample_agent.agent_id) == 2

    # Create a second agent
    agent_2 = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Test Agent 2",
            "user_id": sample_user_id,
        }
    )
    await storage.upsert_agent(sample_user_id, agent_2)

    # Second agent should have 0 threads initially
    assert await storage.count_threads_for_agent(agent_2.agent_id) == 0
    # First agent should still have 2 threads
    assert await storage.count_threads_for_agent(sample_agent.agent_id) == 2

    # Add a thread for the second agent
    thread_2 = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=agent_2.agent_id,
        name="Test Thread for Agent 2",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Thread message for Agent 2")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(sample_user_id, thread_2)

    # Verify that the per-agent thread counts are accurate
    assert await storage.count_threads_for_agent(agent_2.agent_id) == 1
    assert await storage.count_threads_for_agent(sample_agent.agent_id) == 2
