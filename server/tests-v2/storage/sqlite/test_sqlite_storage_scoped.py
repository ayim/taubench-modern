import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.storage import ScopedStorage
from agent_server_types_v2.thread import Thread
from sema4ai_agent_server.storage.v2.errors_v2 import (
    ReferenceIntegrityError,
    ScopedStorageNotFoundError,
)
from sema4ai_agent_server.storage.v2.sqlite_v2 import SQLiteStorageV2


@pytest.mark.asyncio
async def test_scoped_storage_crud_operations(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test create, get, list, upsert, and delete operations for a scoped storage record.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    sample_scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "value"},
    )
    # Create scoped storage
    await storage.create_scoped_storage_v2(sample_scoped_storage)
    fetched = await storage.get_scoped_storage_v2(sample_scoped_storage.storage_id)
    assert fetched is not None
    assert fetched.storage_id == sample_scoped_storage.storage_id
    assert fetched.storage["key"] == "value"

    # List by scope_type and scope_id
    storages = await storage.list_scoped_storage_v2("user", sample_user_id)
    assert any(s.storage_id == sample_scoped_storage.storage_id for s in storages)

    # Upsert: modify the stored dict and update
    updated_scoped_storage = ScopedStorage.from_dict(
        sample_scoped_storage.to_json_dict() | {
            "storage": {"key": "new_value"},
            "updated_at": datetime.now(UTC),
        },
    )
    await storage.upsert_scoped_storage_v2(updated_scoped_storage)
    updated = await storage.get_scoped_storage_v2(sample_scoped_storage.storage_id)
    assert updated.storage["key"] == "new_value"

    # Delete the scoped storage record
    await storage.delete_scoped_storage_v2(sample_scoped_storage.storage_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(sample_scoped_storage.storage_id)

    with pytest.raises(ScopedStorageNotFoundError):
        await storage.delete_scoped_storage_v2(sample_scoped_storage.storage_id)


@pytest.mark.asyncio
async def test_scoped_storage_list_empty(
    storage: SQLiteStorageV2,
) -> None:
    """
    Verify that listing scoped storage for a nonexistent scope returns an empty list.
    """
    storages = await storage.list_scoped_storage_v2("user", "00000000-0000-0000-0000-000000000000")
    assert storages == []


@pytest.mark.asyncio
async def test_scoped_storage_update_timestamp(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that updating a scoped storage record results in an updated_at timestamp
    that is later than the original.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    sample_scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="agent",
        storage={"key": "initial"},
    )
    await storage.create_scoped_storage_v2(sample_scoped_storage)
    fetched = await storage.get_scoped_storage_v2(sample_scoped_storage.storage_id)
    original_updated = fetched.updated_at

    # Pause briefly to ensure a later timestamp.
    await asyncio.sleep(0.01)
    updated_scoped_storage = ScopedStorage.from_dict(
        fetched.to_json_dict()
        | {"storage": {"key": "updated"}, "updated_at": datetime.now(UTC)},
    )
    await storage.upsert_scoped_storage_v2(updated_scoped_storage)
    fetched_after = await storage.get_scoped_storage_v2(sample_scoped_storage.storage_id)
    assert fetched_after.updated_at > original_updated



@pytest.mark.asyncio
async def test_scoped_storage_not_found_error(
    storage: SQLiteStorageV2,
) -> None:
    """
    Test that deleting a non-existent scoped storage record raises ScopedStorageNotFoundError.
    """
    non_existent_storage_id = str(uuid4())
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(non_existent_storage_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.delete_scoped_storage_v2(non_existent_storage_id)



@pytest.mark.asyncio
async def test_scoped_storage_multiple_records_listing(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create several scoped storage records under the same scope type and scope id,
    then list them to verify that all records are returned.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    scope_type = "thread"
    records = []
    for i in range(3):
        record = ScopedStorage(
            storage_id=str(uuid4()),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            created_by_user_id=sample_user_id,
            created_by_agent_id=sample_agent.agent_id,
            created_by_thread_id=sample_thread.thread_id,
            scope_type=scope_type,
            storage={"key": f"value_{i}"},
        )
        records.append(record)
        await storage.create_scoped_storage_v2(record)

    listed = await storage.list_scoped_storage_v2(scope_type, sample_thread.thread_id)
    assert len(listed) == len(records)
    retrieved_ids = {rec.storage_id for rec in listed}
    for rec in records:
        assert rec.storage_id in retrieved_ids


@pytest.mark.asyncio
async def test_scoped_storage_immutable_created_by_fields(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Verify that when updating a scoped storage record, the 'created_by' fields remain unchanged.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    original = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "initial"},
    )
    await storage.create_scoped_storage_v2(original)
    # Store the original IDs for later comparison
    original_user_id = original.created_by_user_id
    original_agent_id = original.created_by_agent_id
    original_thread_id = original.created_by_thread_id
    
    updated = ScopedStorage.from_dict(
        original.to_json_dict() | {"storage": {"key": "updated"}, "updated_at": datetime.now(UTC)},
    )
    await storage.upsert_scoped_storage_v2(updated)
    fetched = await storage.get_scoped_storage_v2(original.storage_id)
    assert fetched.created_by_user_id == original_user_id
    assert fetched.created_by_agent_id == original_agent_id
    assert fetched.created_by_thread_id == original_thread_id
    assert fetched.storage["key"] == "updated"


@pytest.mark.asyncio
async def test_scoped_storage_concurrent_updates(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Simulate concurrent updates to the same scoped storage record and verify the final state is valid.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    original = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="thread",
        storage={"counter": 0},
    )
    await storage.create_scoped_storage_v2(original)

    async def update_storage(increment: int):
        # Each updater reads the record, increments the counter, and writes it back.
        for _ in range(5):
            rec = await storage.get_scoped_storage_v2(original.storage_id)
            new_value = rec.storage.get("counter", 0) + increment
            updated = ScopedStorage.from_dict(
                rec.to_json_dict() | {"storage": {"counter": new_value}, "updated_at": datetime.now(UTC)},
            )
            await storage.upsert_scoped_storage_v2(updated)

    # Run three updaters concurrently.
    await asyncio.gather(
        update_storage(1),
        update_storage(2),
        update_storage(3),
    )
    final_rec = await storage.get_scoped_storage_v2(original.storage_id)
    # Because concurrent updates may interleave, we cannot predict the final value exactly.
    # At minimum, we check that the final counter is an integer.
    assert isinstance(final_rec.storage["counter"], int)


@pytest.mark.asyncio
async def test_scoped_storage_invalid_json_in_storage_field(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Attempt to update a scoped storage record with an invalid JSON structure
    (e.g. including an unserializable object) and verify that a TypeError is raised.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    original = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="thread",
        storage={"key": "initial"},
    )
    await storage.create_scoped_storage_v2(original)
    # Create an update with an unserializable object (a set).
    updated_data = original.to_json_dict()
    updated_data["storage"] = {"key": {"unserializable": set([1, 2, 3])}}
    updated = ScopedStorage.from_dict(updated_data)
    with pytest.raises(TypeError):
        await storage.upsert_scoped_storage_v2(updated)


@pytest.mark.asyncio
async def test_scoped_storage_cross_scope_isolation(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Create scoped storage records with different scope types but the same scope id,
    then verify that listing by a given scope type returns only records for that scope.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    record1 = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "A"},
    )
    record2 = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="agent",
        storage={"key": "B"},
    )
    await storage.create_scoped_storage_v2(record1)
    await storage.create_scoped_storage_v2(record2)

    listed_type_user = await storage.list_scoped_storage_v2("user", sample_user_id)
    assert any(rec.storage_id == record1.storage_id for rec in listed_type_user)
    assert all(rec.scope_type == "user" for rec in listed_type_user)

    listed_type_agent = await storage.list_scoped_storage_v2("agent", sample_agent.agent_id)
    assert any(rec.storage_id == record2.storage_id for rec in listed_type_agent)
    assert all(rec.scope_type == "agent" for rec in listed_type_agent)


@pytest.mark.asyncio
async def test_scoped_storage_recreation_after_deletion(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Delete a scoped storage record and then re-create a record with the same storage ID.
    Verify that the new record is correctly inserted and its audit fields reflect the new creation.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    storage_id = str(uuid4())
    original = ScopedStorage(
        storage_id=storage_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "first"},
    )
    await storage.create_scoped_storage_v2(original)
    # Delete the record.
    await storage.delete_scoped_storage_v2(storage_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(storage_id)
    # Re-create a record with the same storage_id.
    other_user, _ = await storage.get_or_create_user_v2(sub="tenant:testing:user:other_user")
    new_record = ScopedStorage(
        storage_id=storage_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=other_user.user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "second"},
    )
    await storage.create_scoped_storage_v2(new_record)
    fetched = await storage.get_scoped_storage_v2(storage_id)
    assert fetched is not None
    assert fetched.storage["key"] == "second"
    # Verify that the audit fields reflect the new creation.
    assert fetched.created_by_user_id == other_user.user_id
    assert fetched.created_by_agent_id == sample_agent.agent_id
    assert fetched.created_by_thread_id == sample_thread.thread_id



@pytest.mark.asyncio
async def test_scoped_storage_foreign_key_errors(
    storage: SQLiteStorageV2, 
    sample_user_id: str, 
    sample_agent: Agent, 
    sample_thread: Thread,
) -> None:
    """
    Verifys that we get a ReferenceIntegrityError when the foreign key reference is invalid.
    (For users first, then agents, then threads.)
    """
    non_existant_user_id = '00000000-0000-0000-0000-000000000000'
    non_existant_agent_id = '00000000-0000-0000-0000-000000000000'
    non_existant_thread_id = '00000000-0000-0000-0000-000000000000'

    # Create a scoped storage record with a user that doesn't exist.
    scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=non_existant_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "value"},
    )
    with pytest.raises(ReferenceIntegrityError):
        await storage.create_scoped_storage_v2(scoped_storage)

    # Create a scoped storage record with an agent that doesn't exist.
    scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=non_existant_agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="agent",
        storage={"key": "value"},
    )
    with pytest.raises(ReferenceIntegrityError):
        await storage.create_scoped_storage_v2(scoped_storage)

    # Create a scoped storage record with a thread that doesn't exist.
    scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=non_existant_thread_id,
        scope_type="thread",
        storage={"key": "value"},
    )
    with pytest.raises(ReferenceIntegrityError):
        await storage.create_scoped_storage_v2(scoped_storage)


@pytest.mark.asyncio
async def test_scoped_storage_cascading_deletes(
    storage: SQLiteStorageV2,
    sample_user_id: str,
    sample_agent: Agent,
    sample_thread: Thread,
) -> None:
    """
    Test that when a user, or agent, or thread is deleted, all scoped storage records
    associated with that user, agent, or thread are also deleted.
    """
    await storage.upsert_agent_v2(sample_user_id, sample_agent)
    await storage.upsert_thread_v2(sample_user_id, sample_thread)

    # Create a scoped storage record for the user.
    scoped_storage = ScopedStorage(
        storage_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        created_by_user_id=sample_user_id,
        created_by_agent_id=sample_agent.agent_id,
        created_by_thread_id=sample_thread.thread_id,
        scope_type="user",
        storage={"key": "value"},
    )

    # Create and verify the record.
    await storage.create_scoped_storage_v2(scoped_storage)
    fetched = await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    assert fetched is not None
    assert fetched.storage["key"] == "value"

    # Delete the user.
    await storage.delete_user_v2(sample_user_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    # Re-create the user / agent / thread (which would have also been deleted)
    new_user, _ = await storage.get_or_create_user_v2("tenant:testing:user:new_user")
    scoped_storage.created_by_user_id = new_user.user_id
    await storage.upsert_agent_v2(new_user.user_id, sample_agent)
    await storage.upsert_thread_v2(new_user.user_id, sample_thread)

    # Create and verify the record.
    await storage.create_scoped_storage_v2(scoped_storage)
    fetched = await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    assert fetched is not None
    assert fetched.storage["key"] == "value"

    # Delete the agent.
    await storage.delete_agent_v2(new_user.user_id, sample_agent.agent_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    # Re-create the user / agent / thread (which would have also been deleted)
    await storage.upsert_agent_v2(new_user.user_id, sample_agent)
    await storage.upsert_thread_v2(new_user.user_id, sample_thread)

    # Create and verify the record.
    await storage.create_scoped_storage_v2(scoped_storage)
    fetched = await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    assert fetched is not None
    assert fetched.storage["key"] == "value"
    
    # Delete the thread.
    await storage.delete_thread_v2(new_user.user_id, sample_thread.thread_id)
    with pytest.raises(ScopedStorageNotFoundError):
        await storage.get_scoped_storage_v2(scoped_storage.storage_id)
    
    