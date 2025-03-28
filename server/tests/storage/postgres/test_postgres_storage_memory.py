import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.memory import Memory
from agent_platform.server.storage.errors import (
    MemoryNotFoundError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_memory_crud_operations(storage: PostgresStorage) -> None:
    """
    Test create, get, list, upsert, and delete operations for a memory record.
    """
    sample_memory = Memory(
        memory_id=str(uuid4()),
        original_text="original memory text",
        contextualized_text="contextualized memory text",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope="test_scope",
        metadata={"scope_id": "scope123"},
        tags=["tag1", "tag2"],
        refs=["ref1"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    # Create the memory record
    await storage.create_memory(sample_memory)
    fetched = await storage.get_memory(sample_memory.memory_id)
    assert fetched is not None
    assert fetched.memory_id == sample_memory.memory_id
    assert fetched.original_text == "original memory text"

    # List memories by scope and scope_id
    memories = await storage.list_memories("test_scope", "scope123")
    assert any(m.memory_id == sample_memory.memory_id for m in memories)

    # Upsert (update) the memory record
    updated_memory = Memory.model_validate(
        sample_memory.model_dump() | {"original_text": "updated original text"},
    )
    await storage.upsert_memory(updated_memory)
    updated = await storage.get_memory(sample_memory.memory_id)
    assert updated.original_text == "updated original text"

    # Delete the memory and verify it no longer exists
    await storage.delete_memory(sample_memory.memory_id)
    with pytest.raises(MemoryNotFoundError):
        await storage.get_memory(sample_memory.memory_id)
    with pytest.raises(MemoryNotFoundError):
        await storage.delete_memory(sample_memory.memory_id)


@pytest.mark.asyncio
async def test_memory_list_empty(storage: PostgresStorage) -> None:
    """
    Test that listing memories for a scope/ID that has no records returns an empty list.
    """
    memories = await storage.list_memories("nonexistent_scope", "no-id")
    assert memories == []


@pytest.mark.asyncio
async def test_memory_concurrent_upsert(storage: PostgresStorage) -> None:
    """
    Test that concurrent upserts on the same memory record
    do not cause corruption and the final state is valid.
    """
    sample_memory = Memory(
        memory_id=str(uuid4()),
        original_text="Initial text",
        contextualized_text="Initial contextualized",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope="concurrent_test",
        metadata={"info": "test"},
        tags=["tag1"],
        refs=["ref1"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(sample_memory)

    async def update_memory(new_text: str) -> None:
        mem = await storage.get_memory(sample_memory.memory_id)
        updated = Memory.model_validate(
            mem.model_dump() | {
                "original_text": new_text,
                "updated_at": datetime.now(UTC),
            },
        )
        await storage.upsert_memory(updated)

    # Run several concurrent upserts.
    await asyncio.gather(
        update_memory("Update 1"),
        update_memory("Update 2"),
        update_memory("Update 3"),
    )
    final_mem = await storage.get_memory(sample_memory.memory_id)
    assert final_mem.original_text in ["Update 1", "Update 2", "Update 3"]


@pytest.mark.asyncio
async def test_memory_deletion_impacts_listing(storage: PostgresStorage) -> None:
    """
    Test that once a memory record is deleted,
    it no longer appears in listings for its scope.
    """
    scope = "memory_test_scope"
    scope_id = "test123"
    memory1 = Memory(
        memory_id=str(uuid4()),
        original_text="Memory 1",
        contextualized_text="Context 1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope=scope,
        metadata={"scope_id": scope_id, "info": "test1"},
        tags=["tag1"],
        refs=["ref1"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    memory2 = Memory(
        memory_id=str(uuid4()),
        original_text="Memory 2",
        contextualized_text="Context 2",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope=scope,
        metadata={"scope_id": scope_id, "info": "test2"},
        tags=["tag2"],
        refs=["ref2"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(memory1)
    await storage.create_memory(memory2)

    memories_before = await storage.list_memories(scope, scope_id)
    mem_ids_before = {m.memory_id for m in memories_before}
    assert memory1.memory_id in mem_ids_before
    assert memory2.memory_id in mem_ids_before

    # Delete memory1 and verify it is removed.
    await storage.delete_memory(memory1.memory_id)
    memories_after = await storage.list_memories(scope, scope_id)
    mem_ids_after = {m.memory_id for m in memories_after}
    assert memory1.memory_id not in mem_ids_after
    assert memory2.memory_id in mem_ids_after


@pytest.mark.asyncio
async def test_memory_not_found_error(storage: PostgresStorage) -> None:
    """
    Test that deleting a non-existent memory record raises MemoryNotFoundError.
    """
    non_existent_memory_id = str(uuid4())
    with pytest.raises(MemoryNotFoundError):
        await storage.get_memory(non_existent_memory_id)
    with pytest.raises(MemoryNotFoundError):
        await storage.delete_memory(non_existent_memory_id)


@pytest.mark.asyncio
async def test_duplicate_memory_creation(storage: PostgresStorage) -> None:
    """
    Attempt to create two memory records with the same memory_id.
    Expect that the second insertion raises an error (e.g. an integrity error)
    or is handled as a duplicate.
    """
    mem_id = str(uuid4())
    memory_record = Memory(
        memory_id=mem_id,
        original_text="Original text",
        contextualized_text="Contextualized text",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope="duplicate_test",
        metadata={"scope_id": "dup123"},
        tags=["tag1"],
        refs=["ref1"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    # Create the memory record once.
    await storage.create_memory(memory_record)

    # Attempt to create the same record a second time.
    with pytest.raises(RecordAlreadyExistsError):
        await storage.create_memory(memory_record)


@pytest.mark.asyncio
async def test_memory_edge_case_field_values(storage: PostgresStorage) -> None:
    """
    Create a memory record with extreme values—very long strings and special characters—
    and verify that it is stored and retrieved correctly.
    """
    long_text = "A" * 10000  # Very long string.
    special_text = "Special characters: !@#$%^&*()_+世界, emojis: 😃🚀"

    memory_record = Memory(
        memory_id=str(uuid4()),
        original_text=long_text + special_text,
        contextualized_text=special_text + long_text,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope="edge_case",
        metadata={"scope_id": "edge123", "info": special_text},
        tags=["long", "special", "edge"],
        refs=["ref_edge"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(memory_record)
    fetched = await storage.get_memory(memory_record.memory_id)
    assert fetched is not None
    assert fetched.original_text == memory_record.original_text
    assert fetched.metadata["info"] == special_text


@pytest.mark.asyncio
async def test_memory_timestamp_update_verification(storage: PostgresStorage) -> None:
    """
    Create a memory record, then update it and verify that the updated_at timestamp
    changes to a later value.
    """
    memory_record = Memory(
        memory_id=str(uuid4()),
        original_text="Timestamp test original",
        contextualized_text="Timestamp test contextualized",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope="timestamp_test",
        metadata={"scope_id": "ts123"},
        tags=["timestamp"],
        refs=["ref_ts"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(memory_record)
    fetched = await storage.get_memory(memory_record.memory_id)
    original_updated_at = fetched.updated_at

    # Wait a moment so that the updated_at can change noticeably.
    await asyncio.sleep(0.01)
    updated_memory = Memory.model_validate(
        fetched.model_dump() | {
            "original_text": "Updated text",
            "updated_at": datetime.now(UTC),
        },
    )
    await storage.upsert_memory(updated_memory)
    updated_fetched = await storage.get_memory(memory_record.memory_id)
    assert updated_fetched.updated_at > original_updated_at
    assert updated_fetched.original_text == "Updated text"


# @pytest.mark.asyncio
# async def test_concurrent_deletion_and_update(storage: PostgresStorage) -> None:
#     """
#     Simulate a race where one coroutine deletes a memory record while another
#     attempts to update it. Verify the outcome based on the
#     actual sequence of operations.
#     """
#     memory_record = Memory(
#         memory_id=str(uuid4()),
#         original_text="Concurrent deletion update",
#         contextualized_text="Concurrent test",
#         created_at=datetime.now(UTC),
#         updated_at=datetime.now(UTC),
#         relevant_until_timestamp=datetime.now(UTC),
#         relevant_after_timestamp=datetime.now(UTC),
#         scope="concurrent_test",
#         metadata={"scope_id": "conc123"},
#         tags=["concurrent"],
#         refs=["ref_conc"],
#         weight=1.0,
#         embedded=False,
#         embedding_id=str(uuid4()),
#     )
#     await storage.create_memory(memory_record)
#     original_updated_at = memory_record.updated_at

#     async def delete_memory():
#         await asyncio.sleep(0.01)
#         delete_time = datetime.now(UTC)
#         try:
#             await storage.delete_memory(memory_record.memory_id)
#             return ("deleted", delete_time)
#         except Exception:
#             return ("delete_failed", delete_time)

#     async def update_memory():
#         await asyncio.sleep(0.01)
#         update_time = datetime.now(UTC)
#         try:
#             current = await storage.get_memory(memory_record.memory_id)
#             if current is None:
#                 return ("not_found", update_time)
#             updated = Memory.model_validate(
#                 current.model_dump() | {
#                     "original_text": "Updated concurrently",
#                     "updated_at": datetime.now(UTC),
#                 },
#             )
#             await storage.upsert_memory(updated)
#             return ("updated", update_time)
#         except Exception:
#             return ("update_failed", update_time)

#     (delete_status, delete_time), (update_status, update_time) = await asyncio.gather(
#         delete_memory(),
#         update_memory(),
#     )

#     # Check the final state based on operation timing
#     if delete_time < update_time:
#         # If delete happened first, then we either shouldn't
#         # find the record or the update re-created it
#         if update_status == "not_found":
#             with pytest.raises(MemoryNotFoundError):
#                 await storage.get_memory(memory_record.memory_id)
#         else:
#             # If the update re-created it, then it should have
#             # a later updated_at timestamp.
#             updated = await storage.get_memory(memory_record.memory_id)
#             assert updated.updated_at > original_updated_at
#     else:
#         # If update happened first, the record should still be deleted
#         assert delete_status == "deleted"
#         with pytest.raises(MemoryNotFoundError):
#             await storage.get_memory(memory_record.memory_id)


@pytest.mark.asyncio
async def test_memory_filtering_by_scope_id(storage: PostgresStorage) -> None:
    """
    Create multiple memory records under the same scope but with
    different metadata values for 'scope_id', then list memories
    for a specific scope_id and verify that only the correct records
    are returned.
    """
    scope = "filter_test"
    target_scope_id = "filter_target"

    memory_target = Memory(
        memory_id=str(uuid4()),
        original_text="Target memory",
        contextualized_text="Target contextual",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope=scope,
        metadata={"scope_id": target_scope_id},
        tags=["filter"],
        refs=["ref_filter"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(memory_target)

    memory_other = Memory(
        memory_id=str(uuid4()),
        original_text="Other memory",
        contextualized_text="Other contextual",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        relevant_until_timestamp=datetime.now(UTC),
        relevant_after_timestamp=datetime.now(UTC),
        scope=scope,
        metadata={"scope_id": "other_filter"},
        tags=["filter"],
        refs=["ref_other"],
        weight=1.0,
        embedded=False,
        embedding_id=str(uuid4()),
    )
    await storage.create_memory(memory_other)

    filtered_memories = await storage.list_memories(scope, target_scope_id)
    filtered_ids = {mem.memory_id for mem in filtered_memories}
    assert memory_target.memory_id in filtered_ids
    assert memory_other.memory_id not in filtered_ids
