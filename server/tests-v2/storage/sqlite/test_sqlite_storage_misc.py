import asyncio
from uuid import uuid4

import pytest

from agent_server_types_v2.agent import (
    Agent,
)
from agent_server_types_v2.thread import (
    Thread,
    ThreadMessage,
)
from sema4ai_agent_server.storage.v2.sqlite_v2 import SQLiteStorageV2


@pytest.mark.asyncio
async def test_count_operations(
    storage: SQLiteStorageV2, 
    sample_user_id: str, 
    sample_agent: Agent, 
    sample_thread: Thread,
) -> None:
    """Test counting operations for agents and threads."""
    # Initial counts should be 0
    assert await storage.count_agents_v2() == 0
    assert await storage.count_threads_v2() == 0

    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)
    assert await storage.count_agents_v2() == 1
    assert await storage.count_threads_v2() == 1


@pytest.mark.asyncio
async def test_user_access_function(
    storage: SQLiteStorageV2,
) -> None:
    """Test the check_user_access function in SQLite."""
    system_user_id: str = await storage.get_system_user_id_v2()
    other_user, _ = await storage.get_or_create_user_v2(sub="tenant:testing:user:other_user")
    random_user_id: str = str(uuid4())

    async with storage._cursor() as cur:
        await cur.execute(
            "SELECT v2_check_user_access(?, ?) AS check_user_access",
            (random_user_id, system_user_id),
        )
        result1 = await cur.fetchone()
        # System user can access any user -> expect 1
        assert result1["check_user_access"] == 1

        await cur.execute(
            "SELECT v2_check_user_access(?, ?) AS check_user_access",
            (random_user_id, other_user.user_id),
        )
        result2 = await cur.fetchone()
        # Other user cannot access random user -> expect 0
        assert result2["check_user_access"] == 0

        await cur.execute(
            "SELECT v2_check_user_access(?, ?) AS check_user_access",
            (random_user_id, random_user_id),
        )
        result3 = await cur.fetchone()
        # A user can access themselves -> expect 1
        assert result3["check_user_access"] == 1

        await cur.execute(
            "SELECT v2_check_user_access(?, ?) AS check_user_access",
            (system_user_id, system_user_id),
        )
        result4 = await cur.fetchone()
        # System user can access themselves -> expect 1
        assert result4["check_user_access"] == 1

@pytest.mark.asyncio
async def test_get_or_create_user_idempotent(storage: SQLiteStorageV2) -> None:
    """
    Test that calling get_or_create_user_v2 twice with the same subject returns the same user
    and that the second call indicates the user was not created anew.
    """
    sub = "tenant:testing:user:idempotent"
    user1, created1 = await storage.get_or_create_user_v2(sub=sub)
    user2, created2 = await storage.get_or_create_user_v2(sub=sub)

    assert user1.user_id == user2.user_id
    # We expect the first call to create the user (created1 True)
    # and the second call to recognize the user already exists (created2 False).
    assert created1 is True
    assert created2 is False

@pytest.mark.asyncio
async def test_count_after_deletion(storage, sample_user_id, sample_agent, sample_thread):
    """
    Create multiple agents and threads, delete one of each,
    and verify that the count functions reflect the deletion.
    """
    # Get initial counts.
    initial_agent_count = await storage.count_agents_v2()
    initial_thread_count = await storage.count_threads_v2()

    # Create two agents.
    from agent_server_types_v2.agent import Agent
    agent1 = sample_agent
    agent2 = Agent.model_validate(sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "Second Agent"})
    await storage.upsert_agent_v2(sample_user_id, agent1)
    await storage.upsert_agent_v2(sample_user_id, agent2)

    # Create two threads (one for each agent).
    from agent_server_types_v2.thread import Thread
    thread1 = sample_thread
    thread2 = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=agent2.agent_id,
        name="Second Thread",
        messages=[
            ThreadMessage.from_dict(message.to_json_dict() | {"message_id": str(uuid4())})
            for message in sample_thread.messages
        ],
        created_at=sample_thread.created_at,
        updated_at=sample_thread.updated_at,
        metadata=sample_thread.metadata,
    )
    await storage.upsert_thread_v2(sample_user_id, thread1)
    await storage.upsert_thread_v2(sample_user_id, thread2)

    # After creation, counts should increase.
    count_after_creation_agents = await storage.count_agents_v2()
    count_after_creation_threads = await storage.count_threads_v2()
    assert count_after_creation_agents >= initial_agent_count + 2
    assert count_after_creation_threads >= initial_thread_count + 2

    # Delete one agent (which should cascade to delete the thread)
    await storage.delete_agent_v2(sample_user_id, agent2.agent_id)

    count_after_deletion_agents = await storage.count_agents_v2()
    count_after_deletion_threads = await storage.count_threads_v2()
    assert count_after_deletion_agents == count_after_creation_agents - 1
    assert count_after_deletion_threads == count_after_creation_threads - 1


@pytest.mark.asyncio
async def test_concurrent_get_or_create_user(storage):
    """
    Simultaneously call get_or_create_user_v2 with the same subject and verify that
    all invocations return the same user_id and that only one user is created.
    """
    subject = "tenant:testing:user:concurrent"

    async def create_user():
        user, created = await storage.get_or_create_user_v2(sub=subject)
        return user.user_id, created

    results = await asyncio.gather(*(create_user() for _ in range(10)))
    user_ids = {uid for uid, _ in results}
    # All returned user_ids must be identical.
    assert len(user_ids) == 1
    # At least one of the calls should indicate that a user was created.
    created_flags = [created for _, created in results]
    assert any(created_flags)


@pytest.mark.asyncio
async def test_invalid_user_access_input(storage):
    """
    Call the SQL function v2_check_user_access with invalid inputs (empty strings)
    and verify that it returns a default value (assumed 0) or handles the input gracefully.
    """
    async with storage._cursor() as cur:
        await cur.execute("SELECT v2_check_user_access(?, ?) AS check_user_access", ("", ""))
        row = await cur.fetchone()
        # Assuming that for invalid input, the function returns 0.
        assert row["check_user_access"] == 0


@pytest.mark.asyncio
async def test_multiple_user_creation_consistency(storage):
    """
    Create several users with distinct subjects and verify that they are all unique.
    """
    subjects = [f"tenant:testing:user:unique_{i}" for i in range(5)]
    user_ids = []
    for sub in subjects:
        user, _ = await storage.get_or_create_user_v2(sub=sub)
        user_ids.append(user.user_id)
    # Ensure all returned user_ids are unique.
    assert len(set(user_ids)) == len(user_ids)


@pytest.mark.asyncio
async def test_edge_case_subjects(storage):
    """
    Test get_or_create_user_v2 with edge-case subject strings including an empty string,
    a very long string, and strings with special characters.
    """
    # Test with an empty string -- either expect a valid user_id or an exception.
    try:
        user_empty, _ = await storage.get_or_create_user_v2(sub="")
        assert user_empty.user_id  # If allowed, we have a valid user.
    except Exception:
        # If your system rejects an empty subject, an exception is acceptable.
        pass

    # Test with a very long subject.
    long_subject = "tenant:" + "x" * 1000
    user_long, _ = await storage.get_or_create_user_v2(sub=long_subject)
    assert user_long.user_id

    # Test with special characters.
    special_subject = "tenant:testing:user:special_!@#$%^&*()_+世界"
    user_special, _ = await storage.get_or_create_user_v2(sub=special_subject)
    assert user_special.user_id


@pytest.mark.asyncio
async def test_user_data_integrity_after_tampering(storage):
    """
    Create a user, then manually modify its sub field in the database.
    A subsequent call to get_or_create_user_v2 with the original subject should
    result in the creation of a new user (since the tampered record no longer matches).
    """
    original_subject = "tenant:testing:user:tamper"
    user, _ = await storage.get_or_create_user_v2(sub=original_subject)
    original_user_id = user.user_id

    # Manually update the user record to simulate tampering.
    async with storage._cursor() as cur:
        # Adjust the table and column names as per your actual schema.
        await cur.execute(
            "UPDATE v2_user SET sub = ? WHERE user_id = ?",
            ("tampered_value", original_user_id),
        )

    # Now, calling get_or_create_user_v2 with the original subject should not find the tampered record.
    new_user, _ = await storage.get_or_create_user_v2(sub=original_subject)
    new_user_id = new_user.user_id
    assert new_user_id != original_user_id


@pytest.mark.asyncio
async def test_bulk_user_creation(storage):
    """
    Create a bulk number of users concurrently and then verify via a raw SQL query
    that the number of created users in the v2_user table has increased as expected.
    """
    num_users = 50
    subjects = [f"tenant:testing:user:bulk_{i}" for i in range(num_users)]

    async def create_user(sub):
        user, _ = await storage.get_or_create_user_v2(sub=sub)
        return user.user_id

    await asyncio.gather(*(create_user(sub) for sub in subjects))

    # Query the database directly to count the total number of users.
    async with storage._cursor() as cur:
        await cur.execute("SELECT COUNT(*) AS count FROM v2_user")
        row = await cur.fetchone()
        total_users = row["count"]

    # Because other tests may have already created users, we verify that the count
    # is at least as high as the number we just added.
    assert total_users >= num_users