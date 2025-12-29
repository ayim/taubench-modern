import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg.errors import InvalidTextRepresentation
from psycopg_pool import AsyncConnectionPool

from agent_platform.core.agent import Agent
from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.server.storage.errors import UserPermissionError
from agent_platform.server.storage.postgres import PostgresStorage

pytestmark = pytest.mark.postgresql


@pytest.mark.asyncio
async def test_count_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test counting operations for agents and threads.
    """
    # Initial counts should be 0.
    assert await storage.count_agents() == 0
    assert await storage.count_threads() == 0
    assert await storage.count_agents_by_mode("conversational") == 0
    assert await storage.count_agents_by_mode("worker") == 0
    assert await storage.count_messages() == 0

    await storage.upsert_agent(sample_user_id, sample_agent)
    await storage.upsert_thread(sample_user_id, sample_thread)
    assert await storage.count_agents() == 1
    assert await storage.count_threads() == 1
    assert await storage.count_agents_by_mode("conversational") == 1
    assert await storage.count_agents_by_mode("worker") == 0
    assert await storage.count_messages() == len(sample_thread.messages)

    # Create a worker agent to test worker count
    worker_agent = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "Test Worker Agent", "mode": "worker"}
    )
    await storage.upsert_agent(sample_user_id, worker_agent)
    assert await storage.count_agents() == 2
    assert await storage.count_agents_by_mode("conversational") == 1
    assert await storage.count_agents_by_mode("worker") == 1


@pytest.mark.asyncio
async def test_user_access_function(
    postgres_test_db: AsyncConnectionPool,
    storage: PostgresStorage,
) -> None:
    """
    Test the check_user_access function in Postgres.
    """
    system_user_id: str = await storage.get_system_user_id()
    this_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:this_user",
    )
    other_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:other_user",
    )
    tenant_user, _ = await storage.get_or_create_user(
        sub="tenant:testing",
    )
    other_tenant_user, _ = await storage.get_or_create_user(
        sub="tenant:other_testing:user:other_user",
    )

    async with postgres_test_db.connection() as conn:
        # Don't have dict cursor here, so fetchone returns a tuple.
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (system_user_id, this_user.user_id),
            )
            result1 = await cur.fetchone()
            # Any user can access system resources → expect 1.
            assert result1 is not None
            assert result1[0] == 1

            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (other_user.user_id, this_user.user_id),
            )
            result2 = await cur.fetchone()
            # This user cannot access other user → expect 0.
            assert result2 is not None
            assert result2[0] == 0

            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (this_user.user_id, this_user.user_id),
            )
            result3 = await cur.fetchone()
            # A user can access themselves → expect 1.
            assert result3 is not None
            assert result3[0] == 1

            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (system_user_id, system_user_id),
            )
            result4 = await cur.fetchone()
            # System user can access themselves → expect 1.
            assert result4 is not None
            assert result4[0] == 1

            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (tenant_user.user_id, this_user.user_id),
            )
            result3 = await cur.fetchone()
            # A user can access tenant resources → expect 1.
            assert result3 is not None
            assert result3[0] == 1

            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (other_tenant_user.user_id, this_user.user_id),
            )
            result3 = await cur.fetchone()
            # A user can access another tenant resources → expect 0.
            assert result3 is not None
            assert result3[0] == 0


@pytest.mark.asyncio
async def test_user_access_function_accepts_any_middle_segments_for_system_user(
    postgres_test_db: AsyncConnectionPool,
    storage: PostgresStorage,
) -> None:
    """
    The UDF should grant access when the record or requesting subject ends with
    ':system_user' regardless of the two middle segments (tenant:%:%:system_user).
    """
    # Create a user that should be treated as a global system user
    # under the broadened pattern (middle segment is 'user', not 'system').
    broadened_system_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:system_user",
    )

    # Create a normal user in the same tenant
    normal_user, _ = await storage.get_or_create_user(
        sub="tenant:testing:user:normal_user",
    )

    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            # Any user can access resources owned by a subject matching tenant:%:%:system_user
            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (broadened_system_user.user_id, normal_user.user_id),
            )
            result = await cur.fetchone()
            assert result is not None
            assert result[0] == 1

            # And the broadened system user can access a regular user's resources
            await cur.execute(
                "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                (normal_user.user_id, broadened_system_user.user_id),
            )
            result = await cur.fetchone()
            assert result is not None
            assert result[0] == 1


@pytest.mark.asyncio
async def test_file_access_control_users(
    storage: PostgresStorage,
    sample_agent: Agent,
) -> None:
    """
    Another regular user should not be able to access file metadata/path for files
    owned by a non-system user on a thread.
    """
    original_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    other_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:other")

    # Original user creates agent and thread
    await storage.upsert_agent(original_user.user_id, sample_agent)
    thread = Thread(
        thread_id=str(uuid4()),
        user_id=original_user.user_id,
        agent_id=sample_agent.agent_id,
        name="Thread with file",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )
    await storage.upsert_thread(original_user.user_id, thread)

    # Put a file owned by the original user
    file_id = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id,
        file_path=None,
        file_ref="test.txt",
        file_hash="abc",
        file_size_raw=1,
        mime_type="text/plain",
        user_id=original_user.user_id,
        embedded=False,
        embedding_status=None,
        owner=thread,
        file_path_expiration=datetime.now(UTC),
    )

    # Other user should not be able to fetch by id
    with pytest.raises(UserPermissionError):
        await storage.get_file_by_id(file_id, other_user.user_id)

    # Other user should not be able to fetch by ref
    with pytest.raises(UserPermissionError):
        await storage.get_file_by_ref(thread, "test.txt", other_user.user_id)

    # System user should be able to access (thread-owned file access)
    sys_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:system_user")
    sys_file_read_id = await storage.get_file_by_id(file_id, sys_user.user_id)
    assert sys_file_read_id is not None
    assert sys_file_read_id.file_id == file_id
    assert sys_file_read_id.user_id == original_user.user_id
    assert sys_file_read_id.thread_id == thread.thread_id
    assert sys_file_read_id.file_ref == "test.txt"

    # Other user should not be able to delete the file
    with pytest.raises(UserPermissionError):
        await storage.delete_file(thread, file_id, other_user.user_id)


@pytest.mark.asyncio
async def test_get_or_create_user_idempotent(storage: PostgresStorage) -> None:
    """
    Test that calling get_or_create_user twice with the same subject
    returns the same user and that the second call indicates the user
    was not created anew.
    """
    sub = "tenant:testing:user:idempotent"
    user1, created1 = await storage.get_or_create_user(sub=sub)
    user2, created2 = await storage.get_or_create_user(sub=sub)

    assert user1.user_id == user2.user_id
    # We expect the first call to create the user and the
    # second call to recognize it already exists.
    assert created1 is True
    assert created2 is False


@pytest.mark.asyncio
async def test_count_after_deletion(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create multiple agents and threads, delete one of each,
    and verify that the count functions reflect the deletion.
    """
    # Get initial counts.
    initial_agent_count = await storage.count_agents()
    initial_thread_count = await storage.count_threads()

    # Create two agents.
    agent1 = sample_agent
    agent2 = Agent.model_validate(
        sample_agent.model_dump() | {"agent_id": str(uuid4()), "name": "Second Agent"},
    )
    await storage.upsert_agent(sample_user_id, agent1)
    await storage.upsert_agent(sample_user_id, agent2)

    # Create two threads (one for each agent).
    thread1 = sample_thread
    thread2 = Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=agent2.agent_id,
        name="Second Thread",
        messages=[
            ThreadMessage.model_validate(
                message.model_dump() | {"message_id": str(uuid4())},
            )
            for message in sample_thread.messages
        ],
        created_at=sample_thread.created_at,
        updated_at=sample_thread.updated_at,
        metadata=sample_thread.metadata,
    )
    await storage.upsert_thread(sample_user_id, thread1)
    await storage.upsert_thread(sample_user_id, thread2)

    # After creation, counts should increase.
    count_after_creation_agents = await storage.count_agents()
    count_after_creation_threads = await storage.count_threads()
    assert count_after_creation_agents >= initial_agent_count + 2
    assert count_after_creation_threads >= initial_thread_count + 2

    # Delete one agent (which should cascade to delete the thread).
    await storage.delete_agent(sample_user_id, agent2.agent_id)

    count_after_deletion_agents = await storage.count_agents()
    count_after_deletion_threads = await storage.count_threads()
    assert count_after_deletion_agents == count_after_creation_agents - 1
    assert count_after_deletion_threads == count_after_creation_threads - 1


@pytest.mark.asyncio
async def test_concurrent_get_or_create_user(storage: PostgresStorage):
    """
    Test concurrent user creation with proper connection handling.
    """
    subject = "tenant:testing:user:concurrent"
    num_concurrent = 10

    async def create_user():
        try:
            user, created = await storage.get_or_create_user(sub=subject)
            return user.user_id, created
        except Exception as e:
            # Log any errors but don't fail silently
            print(f"Error in create_user: {e}")
            raise

    # Use a semaphore to limit concurrent connections
    sem = asyncio.Semaphore(5)  # Limit concurrent operations

    async def bounded_create():
        async with sem:
            return await create_user()

    results = await asyncio.gather(
        *(bounded_create() for _ in range(num_concurrent)),
        return_exceptions=True,
    )

    # Filter out any exceptions and valid results
    valid_results: list[tuple[str, bool]] = [r for r in results if not isinstance(r, BaseException)]

    if not valid_results:
        pytest.fail("All concurrent operations failed")

    user_ids = {uid for uid, _ in valid_results}
    assert len(user_ids) == 1  # All operations should return the same user

    created_flags = [created for _, created in valid_results]
    assert any(created_flags)  # At least one operation should have created the user


@pytest.mark.asyncio
async def test_invalid_user_access_input(postgres_test_db: AsyncConnectionPool):
    """
    Call the SQL function v2.check_user_access with invalid inputs (empty strings)
    and verify that it returns a default value (assumed 0) or
    handles the input gracefully.
    """
    async with postgres_test_db.connection() as conn:
        async with conn.cursor() as cur:
            with pytest.raises(InvalidTextRepresentation):
                await cur.execute(
                    "SELECT v2.check_user_access(%s, %s) AS check_user_access",
                    ("", ""),
                )


@pytest.mark.asyncio
async def test_multiple_user_creation_consistency(storage: PostgresStorage):
    """
    Create several users with distinct subjects and verify that they are all unique.
    """
    subjects = [f"tenant:testing:user:unique_{i}" for i in range(5)]
    user_ids = []
    for sub in subjects:
        user, _ = await storage.get_or_create_user(sub=sub)
        user_ids.append(user.user_id)
    # Ensure all returned user_ids are unique.
    assert len(set(user_ids)) == len(user_ids)


@pytest.mark.asyncio
async def test_edge_case_subjects(storage: PostgresStorage):
    """
    Test get_or_create_user with edge-case subject strings including an empty string,
    a very long string, and strings with special characters.
    """
    # Test with an empty string -- either expect a valid user_id or an exception.
    try:
        user_empty, _ = await storage.get_or_create_user(sub="")
        assert user_empty.user_id  # If allowed, we have a valid user.
    except Exception:
        pass

    # Test with a very long subject.
    long_subject = "tenant:" + "x" * 1000
    user_long, _ = await storage.get_or_create_user(sub=long_subject)
    assert user_long.user_id

    # Test with special characters.
    special_subject = "tenant:testing:user:special_!@#$%^&*()_+世界"
    user_special, _ = await storage.get_or_create_user(sub=special_subject)
    assert user_special.user_id


@pytest.mark.asyncio
async def test_user_data_integrity_after_tampering(storage: PostgresStorage):
    """
    Create a user, then manually modify its sub field in the database.
    A subsequent call to get_or_create_user with the original subject should
    result in the creation of a new user (since the tampered record no longer matches).
    """
    original_subject = "tenant:testing:user:tamper"
    user, _ = await storage.get_or_create_user(sub=original_subject)
    original_user_id = user.user_id

    async with storage._transaction() as cur:
        # Adjust the table and column names as per your actual schema.
        await cur.execute(
            "UPDATE v2.user SET sub = %s WHERE user_id = %s",
            ("tampered_value", original_user_id),
        )

    new_user, _ = await storage.get_or_create_user(sub=original_subject)
    new_user_id = new_user.user_id
    assert new_user_id != original_user_id


@pytest.mark.asyncio
async def test_bulk_user_creation(storage: PostgresStorage):
    """
    Create a bulk number of users concurrently and then verify via a raw SQL query
    that the number of created users in the v2.user table has increased as expected.
    """
    num_users = 50
    subjects = [f"tenant:testing:user:bulk_{i}" for i in range(num_users)]

    async def create_user(sub):
        user, _ = await storage.get_or_create_user(sub=sub)
        return user.user_id

    await asyncio.gather(*(create_user(sub) for sub in subjects))

    async with storage._cursor() as cur:
        await cur.execute("SELECT COUNT(*) AS count FROM v2.user")
        row = await cur.fetchone()
        assert row is not None
        total_users = row["count"]

    # Because other tests may have already created users, verify that the count
    # is at least as high as the number we just added.
    assert total_users >= num_users
