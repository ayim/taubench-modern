import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.runbook import Runbook
from agent_platform.core.thread import Thread, ThreadMessage, ThreadTextContent
from agent_platform.server.storage.errors import (
    InvalidUUIDError,
    ThreadNotFoundError,
)
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_thread_crud_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """Test Create, Read, Update, and Delete operations for threads."""
    # Create (ensure the agent exists first)
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)
    # Read
    retrieved_thread = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert retrieved_thread is not None
    assert retrieved_thread.thread_id == sample_thread.thread_id
    assert retrieved_thread.name == sample_thread.name

    # Update: modify the thread's name
    updated_thread = sample_thread.copy()
    updated_thread.name = "Updated Thread Name"
    await storage.upsert_thread(sample_user_id, updated_thread)
    retrieved_updated = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert retrieved_updated is not None
    assert retrieved_updated.name == "Updated Thread Name"

    # Delete the thread and confirm deletion
    await storage.delete_thread(sample_user_id, sample_thread.thread_id)
    with pytest.raises(ThreadNotFoundError):
        await storage.get_thread(sample_user_id, sample_thread.thread_id)


@pytest.mark.asyncio
async def test_thread_add_message(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that adding a message to an existing thread appends the message properly.
    """
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)

    # Create a new message to add.
    additional_message = ThreadMessage(
        role="user",
        content=[ThreadTextContent(text="This is an additional message")],
    )
    await storage.add_message_to_thread(
        sample_user_id,
        sample_thread.thread_id,
        additional_message,
    )

    # Retrieve the thread and verify that the new message was appended.
    updated_thread = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert updated_thread is not None
    # Expect one more message than originally seeded.
    assert len(updated_thread.messages) == len(sample_thread.messages) + 1
    # Verify that the last message is the one we just added.
    last_message = updated_thread.messages[-1]
    assert len(last_message.content) > 0
    assert isinstance(last_message.content[0], ThreadTextContent)
    assert last_message.content[0].text == "This is an additional message"


@pytest.mark.asyncio
async def test_list_threads_for_agent(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """Test listing threads for a specific agent."""
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)
    threads = await storage.list_threads_for_agent(
        sample_user_id,
        sample_agent.agent_id,
    )
    assert len(threads) == 1
    assert threads[0].thread_id == sample_thread.thread_id
    assert threads[0].agent_id == sample_agent.agent_id


@pytest.mark.asyncio
async def test_thread_message_ordering(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test that thread messages maintain their order after storage and retrieval."""
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Message Order Test",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text=f"Message {i}")],
            )
            for i in range(5)
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)
    retrieved = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved is not None
    assert len(retrieved.messages) == 5
    for i, msg in enumerate(retrieved.messages):
        assert len(msg.content) > 0
        assert isinstance(msg.content[0], ThreadTextContent)
        assert msg.content[0].text == f"Message {i}"


@pytest.mark.asyncio
async def test_thread_complex_json_metadata(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test storage and retrieval of complex JSON metadata structures."""
    complex_metadata = {
        "nested": {
            "array": [1, 2, {"key": "value"}],
            "null_value": None,
            "bool_value": True,
            "special_chars": "Hello 世界 🌍",
        },
    }
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Complex JSON Test",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata=complex_metadata,
    )
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)
    retrieved = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved is not None
    assert retrieved.metadata == complex_metadata


@pytest.mark.asyncio
async def test_thread_concurrent_updates(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test concurrent updates to the same thread."""
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Concurrent Test",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)

    async def update_thread(name: str) -> None:
        # Create a copy, update its name, and write it back.
        thread_copy = Thread.model_validate(thread.model_dump())
        thread_copy.name = name
        await storage.upsert_thread(sample_user_id, thread_copy)

    await asyncio.gather(
        update_thread("Update 1"),
        update_thread("Update 2"),
        update_thread("Update 3"),
    )
    retrieved = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved is not None
    # Since concurrent updates may interleave, check that
    # the final name is one of the updates.
    assert retrieved.name in ["Update 1", "Update 2", "Update 3"]


@pytest.mark.asyncio
async def test_thread_error_cases(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test various error cases and edge conditions."""
    # Test: fetching a thread with an invalid UUID should raise an error.
    with pytest.raises(InvalidUUIDError):
        await storage.get_thread(sample_user_id, "not-a-uuid")

    # Test: listing agents for a non-existent user should return an empty list.
    non_existent_user: str = str(uuid4())
    agents = await storage.list_agents(non_existent_user)
    assert len(agents) == 0

    # Test: a thread created with empty messages remains empty.
    await storage.upsert_agent(sample_user_id, sample_agent)
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Empty Messages",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )
    await storage.upsert_thread(sample_user_id, thread)
    retrieved = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved is not None
    assert len(retrieved.messages) == 0


@pytest.mark.asyncio
async def test_thread_listing_with_multiple_agents(
    storage: PostgresStorage,
    sample_user_id: str,
) -> None:
    """Test listing threads across multiple agents."""
    agents = [
        Agent(
            agent_id=str(uuid4()),
            user_id=sample_user_id,
            name=f"Agent {i}",
            description="Test",
            runbook=Runbook(raw_text="test", content=[]),
            version="1.0.0",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            action_packages=[],
            agent_architecture=AgentArchitecture(name="test", version="1.0.0"),
            question_groups=[],
            observability_configs=[],
            platform_configs=[],
            extra={},
        )
        for i in range(3)
    ]
    # Create multiple agents each with multiple threads
    for agent in agents:
        await storage.upsert_agent(sample_user_id, agent)
        for j in range(2):
            thread = Thread(
                thread_id=str(uuid4()),
                user_id=sample_user_id,
                agent_id=agent.agent_id,
                name=f"Thread {j} for Agent {agent.name}",
                messages=[],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                metadata={},
            )
            await storage.upsert_thread(sample_user_id, thread)
    # Should have 3 agents * 2 threads each = 6 total threads
    all_threads = await storage.list_threads(sample_user_id)
    assert len(all_threads) == 6

    # Test listing threads for the first agent
    agent_threads = await storage.list_threads_for_agent(
        sample_user_id,
        agents[0].agent_id,
    )
    assert len(agent_threads) == 2
    for t in agent_threads:
        assert t.agent_id == agents[0].agent_id


@pytest.mark.asyncio
async def test_thread_deletion_nonexistent(
    storage: PostgresStorage,
    sample_user_id: str,
) -> None:
    """
    Test that attempting to delete a non-existent thread raises ThreadNotFoundError.
    """
    non_existent_thread_id = str(uuid4())
    with pytest.raises(ThreadNotFoundError):
        await storage.delete_thread(sample_user_id, non_existent_thread_id)


@pytest.mark.asyncio
async def test_thread_add_message_to_nonexistent(
    storage: PostgresStorage,
    sample_user_id: str,
) -> None:
    """
    Test that attempting to add a message to a non-existent thread
    raises ThreadNotFoundError.
    """
    non_existent_thread_id = str(uuid4())
    additional_message = ThreadMessage(
        role="user",
        content=[ThreadTextContent(text="Message for non-existent thread")],
    )
    with pytest.raises(ThreadNotFoundError):
        await storage.add_message_to_thread(
            sample_user_id,
            non_existent_thread_id,
            additional_message,
        )
