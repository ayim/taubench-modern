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
    UserAccessDeniedError,
    UserPermissionError,
)
from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_thread_crud_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """Test Create, Read, Update, and Delete operations for threads."""
    # Create (need agent first)
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

    # Update
    updated_thread = sample_thread.copy()
    updated_thread.name = "Updated Thread Name"
    await storage.upsert_thread(sample_user_id, updated_thread)
    retrieved_updated = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert retrieved_updated is not None
    assert retrieved_updated.name == "Updated Thread Name"

    # Delete
    await storage.delete_thread(sample_user_id, sample_thread.thread_id)
    with pytest.raises(ThreadNotFoundError):
        await storage.get_thread(sample_user_id, sample_thread.thread_id)


@pytest.mark.asyncio
async def test_thread_add_message(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that adding a message to an existing thread using add_message_to_thread
    appends the message properly.
    """
    # Ensure the agent and thread exist.
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

    # Retrieve the thread and verify the message was appended.
    updated_thread = await storage.get_thread(
        sample_user_id,
        sample_thread.thread_id,
    )
    assert updated_thread is not None
    # Expect one more message than originally seeded.
    assert len(updated_thread.messages) == len(sample_thread.messages) + 1
    # Verify that the last message matches the additional message.
    last_message = updated_thread.messages[-1]
    assert len(last_message.content) > 0
    assert isinstance(last_message.content[0], ThreadTextContent)
    assert last_message.content[0].text == "This is an additional message"


@pytest.mark.asyncio
async def test_list_threads_for_agent(
    storage: SQLiteStorage,
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
    storage: SQLiteStorage,
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
    storage: SQLiteStorage,
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
    storage: SQLiteStorage,
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
    assert retrieved.name in ["Update 1", "Update 2", "Update 3"]


@pytest.mark.asyncio
async def test_thread_error_cases(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test various error cases and edge conditions."""
    # Test invalid UUID
    with pytest.raises(InvalidUUIDError):
        await storage.get_agent(sample_user_id, "not-a-uuid")

    # Test non-existent user
    non_existent_user: str = str(uuid4())
    agents = await storage.list_agents(non_existent_user)
    assert len(agents) == 0

    # Test empty thread messages
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
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """Test listing threads across multiple agents."""
    agents = [
        Agent(
            agent_id=str(uuid4()),
            user_id=sample_user_id,
            name=f"Agent {i}",
            description="Test",
            runbook_structured=Runbook(raw_text="test", content=[]),
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
    storage: SQLiteStorage,
    sample_user_id: str,
) -> None:
    """
    Test that attempting to delete a non-existent thread raises ThreadNotFoundError.
    """
    non_existent_thread_id = str(uuid4())
    with pytest.raises(ThreadNotFoundError):
        await storage.delete_thread(sample_user_id, non_existent_thread_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_sub", "caller_sub", "expect_error"),
    [
        ("tenant:testing:user:owner", "tenant:testing:user:other", True),
        ("tenant:testing:system:system_user", "tenant:testing:user:other", False),
        ("tenant:testing:user:owner", "tenant:testing:system:system_user", False),
        ("tenant:testing:user:owner", "tenant:testing:user:system_user", False),
        ("tenant:testing:user:system_user", "tenant:testing:user:other", False),
    ],
)
async def test_thread_access_control_users(
    storage: SQLiteStorage,
    sample_agent: Agent,
    owner_sub: str,
    caller_sub: str,
    expect_error: bool,
) -> None:
    """
    Validate access rules for threads where the owner may be a regular user or a system user.
    When the owner is a system user, other users have access.
    """
    owner_user, _ = await storage.get_or_create_user(sub=owner_sub)
    caller_user, _ = await storage.get_or_create_user(sub=caller_sub)

    # Owner creates agent and thread
    await storage.upsert_agent(owner_user.user_id, sample_agent)
    owner_thread = Thread(
        thread_id=str(uuid4()),
        user_id=owner_user.user_id,
        agent_id=sample_agent.agent_id,
        name="Owner Thread",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )
    await storage.upsert_thread(owner_user.user_id, owner_thread)

    if expect_error:
        # Caller cannot read or update
        with pytest.raises(UserAccessDeniedError):
            await storage.get_thread(caller_user.user_id, owner_thread.thread_id)
        updated = Thread.model_validate(owner_thread.model_dump() | {"name": "Hacked Name"})
        with pytest.raises(UserAccessDeniedError):
            await storage.upsert_thread(caller_user.user_id, updated)
    else:
        # Caller can read and update
        read = await storage.get_thread(caller_user.user_id, owner_thread.thread_id)
        assert read is not None
        updated = Thread.model_validate(owner_thread.model_dump() | {"name": "Caller Update"})
        await storage.upsert_thread(caller_user.user_id, updated)

    # Owner can still read
    read_back = await storage.get_thread(owner_user.user_id, owner_thread.thread_id)
    assert read_back is not None


@pytest.mark.asyncio
async def test_thread_add_message_to_nonexistent(
    storage: SQLiteStorage,
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


@pytest.mark.asyncio
async def test_delete_threads_for_agent(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test deleting all threads for an agent and deleting specific
    threads by thread_ids."""
    # Create a regular user for the main user
    main_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:main_user",
    )
    main_user_id = main_user.user_id

    # Create agent first
    await storage.upsert_agent(main_user_id, sample_agent)

    # Create multiple threads for the agent
    threads = []
    for i in range(3):
        thread = Thread(
            thread_id=str(uuid4()),
            user_id=main_user_id,
            agent_id=sample_agent.agent_id,
            name=f"Thread {i}",
            messages=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata={},
        )
        threads.append(thread)
        await storage.upsert_thread(main_user_id, thread)

    # Create threads for another user with the same agent
    other_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:other_user",
    )
    other_user_id = other_user.user_id

    other_user_threads = []
    for i in range(2):
        thread = Thread(
            thread_id=str(uuid4()),
            user_id=other_user_id,
            agent_id=sample_agent.agent_id,
            name=f"Other User Thread {i}",
            messages=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata={},
        )
        other_user_threads.append(thread)
        await storage.upsert_thread(other_user_id, thread)

    # Verify threads were created
    retrieved_threads = await storage.list_threads_for_agent(
        main_user_id,
        sample_agent.agent_id,
    )
    assert len(retrieved_threads) == 3

    other_user_retrieved_threads = await storage.list_threads_for_agent(
        other_user_id,
        sample_agent.agent_id,
    )
    assert len(other_user_retrieved_threads) == 2

    # Delete all threads for the agent
    await storage.delete_threads_for_agent(
        main_user_id,
        sample_agent.agent_id,
    )
    retrieved_threads = await storage.list_threads_for_agent(
        main_user_id,
        sample_agent.agent_id,
    )
    assert len(retrieved_threads) == 0

    # Verify other user's threads are unaffected
    other_user_retrieved_threads = await storage.list_threads_for_agent(
        other_user_id,
        sample_agent.agent_id,
    )
    assert len(other_user_retrieved_threads) == 2

    # Recreate threads
    for thread in threads:
        await storage.upsert_thread(main_user_id, thread)

    # Delete specific threads by thread_ids
    thread_ids_to_delete = [threads[0].thread_id, threads[2].thread_id]
    await storage.delete_threads_for_agent(
        main_user_id,
        sample_agent.agent_id,
        thread_ids_to_delete,
    )
    retrieved_threads = await storage.list_threads_for_agent(
        main_user_id,
        sample_agent.agent_id,
    )
    assert len(retrieved_threads) == 1
    assert retrieved_threads[0].thread_id == threads[1].thread_id

    # Verify other user's threads are still unaffected
    other_user_retrieved_threads = await storage.list_threads_for_agent(
        other_user_id,
        sample_agent.agent_id,
    )
    assert len(other_user_retrieved_threads) == 2


@pytest.mark.asyncio
async def test_trim_messages_from_sequence_with_invalid_message_id(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test trimming messages from a sequence with invalid message ID (agent role)."""
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Edit Message Test",
        messages=[],
    )
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)

    # Add multiple messages to the thread
    message1 = ThreadMessage(role="user", content=[ThreadTextContent(text="Hello")])
    message2 = ThreadMessage(role="agent", content=[ThreadTextContent(text="Hi there!")])
    message3 = ThreadMessage(role="user", content=[ThreadTextContent(text="How are you?")])
    message4 = ThreadMessage(role="agent", content=[ThreadTextContent(text="I'm good, thanks!")])
    message5 = ThreadMessage(role="user", content=[ThreadTextContent(text="What's your name?")])
    message6 = ThreadMessage(role="agent", content=[ThreadTextContent(text="My name is John Doe")])

    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message1)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message2)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message3)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message4)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message5)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message6)

    # Get the thread to access message IDs
    thread_before_trim = await storage.get_thread(sample_user_id, thread.thread_id)
    assert thread_before_trim is not None
    assert len(thread_before_trim.messages) == 6

    # Try to trim from an agent message (message2) - this should fail
    agent_message_id = thread_before_trim.messages[1].message_id  # This is an agent message
    with pytest.raises(UserPermissionError):
        await storage.trim_messages_from_sequence(
            sample_user_id,
            thread.thread_id,
            agent_message_id,
        )

    # Check that messages before the trim point remain (message1 and message2)
    retrieved_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved_thread is not None
    assert len(retrieved_thread.messages) == 6


@pytest.mark.asyncio
async def test_trim_messages_from_sequence(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test trimming messages from a sequence."""
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Edit Message Test",
        messages=[],
    )
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)

    # Add multiple messages to the thread
    message1 = ThreadMessage(role="user", content=[ThreadTextContent(text="Hello")])
    message2 = ThreadMessage(role="agent", content=[ThreadTextContent(text="Hi there!")])
    message3 = ThreadMessage(role="user", content=[ThreadTextContent(text="How are you?")])
    message4 = ThreadMessage(role="agent", content=[ThreadTextContent(text="I'm good, thanks!")])
    message5 = ThreadMessage(role="user", content=[ThreadTextContent(text="What's your name?")])
    message6 = ThreadMessage(role="agent", content=[ThreadTextContent(text="My name is John Doe")])

    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message1)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message2)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message3)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message4)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message5)
    await storage.add_message_to_thread(sample_user_id, thread.thread_id, message6)

    # Get the thread to access message IDs
    thread_before_trim = await storage.get_thread(sample_user_id, thread.thread_id)
    assert thread_before_trim is not None
    assert len(thread_before_trim.messages) == 6

    # Trim from the second message (should remove message2, message3, message4,
    # and message5, keeping only message1)
    third_message_id = thread_before_trim.messages[2].message_id
    await storage.trim_messages_from_sequence(
        sample_user_id,
        thread.thread_id,
        third_message_id,
    )

    # Check that only the first and second message remain
    retrieved_thread = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved_thread is not None
    assert len(retrieved_thread.messages) == 2
    assert isinstance(retrieved_thread.messages[0].content[0], ThreadTextContent)
    assert retrieved_thread.messages[0].content[0].text == "Hello"
    assert isinstance(retrieved_thread.messages[1].content[0], ThreadTextContent)
    assert retrieved_thread.messages[1].content[0].text == "Hi there!"


@pytest.mark.asyncio
async def test_thread_messages_commited_complete_flags(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Test that thread messages retrieved from storage have commited=True and complete=True."""
    # Create a thread with messages
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Test Commited/Complete Flags",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="User message")],
                commited=False,  # Set to False initially
                complete=False,  # Set to False initially
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="Agent response")],
                commited=False,  # Set to False initially
                complete=False,  # Set to False initially
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )

    # Store the thread
    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, thread)

    # Retrieve the thread
    retrieved = await storage.get_thread(sample_user_id, thread.thread_id)
    assert retrieved is not None
    assert len(retrieved.messages) == 2

    # Check that both messages have commited=True and complete=True
    for msg in retrieved.messages:
        assert msg.commited is True, "Messages retrieved from database should have commited=True"
        assert msg.complete is True, "Messages retrieved from database should have complete=True"
        # Also check that content items are marked complete
        for content in msg.content:
            assert content.complete is True, "Content items should also be marked complete"

    # Test model_dump includes commited field
    for msg in retrieved.messages:
        dumped = msg.model_dump()
        assert "commited" in dumped, "model_dump should include commited field"
        assert dumped["commited"] is True
        assert "complete" in dumped, "model_dump should include complete field"
        assert dumped["complete"] is True


@pytest.mark.asyncio
async def test_delete_thread_other_user(
    storage: SQLiteStorage,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """Test that a thread cannot be deleted by a non-owner user."""
    owner, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    agent = Agent.model_validate(sample_agent.model_dump() | {"user_id": owner.user_id})
    thread = Thread.model_validate(sample_thread.model_dump() | {"user_id": owner.user_id})
    await storage.upsert_agent(owner.user_id, agent)
    await storage.upsert_thread(owner.user_id, thread)

    other_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:other")
    with pytest.raises(UserAccessDeniedError):
        await storage.delete_thread(other_user.user_id, thread.thread_id)
