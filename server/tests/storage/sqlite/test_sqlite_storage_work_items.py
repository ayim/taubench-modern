from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCallback,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.storage.errors import WorkItemFileNotFoundError
from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_create_and_get_work_item(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Create a work item and retrieve it back from SQLite storage."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
        # Provide a minimal message list to exercise JSON (de)serialization
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello!")],
            ),
        ],
        payload={"foo": "bar"},
    )

    await storage.create_work_item(work_item)

    fetched = await storage.get_work_item(work_item.work_item_id)
    assert fetched is not None
    assert fetched.work_item_id == work_item.work_item_id
    assert fetched.agent_id == work_item.agent_id
    assert fetched.status == WorkItemStatus.PENDING
    assert fetched.payload == work_item.payload
    # Messages round-trip
    assert len(fetched.messages) == 1
    assert fetched.messages[0].content[0].model_dump()["text"] == "Hello!"


@pytest.mark.asyncio
async def test_work_item_subject_field(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test that the user_subject field is properly populated with user's sub."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Get the user to verify their sub
    user, _ = await storage.get_or_create_user(sample_user_id)

    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Subject test!")],
            ),
        ],
        payload={"test": "user_subject"},
    )

    await storage.create_work_item(work_item)

    # Retrieve and verify user_subject field is populated
    fetched = await storage.get_work_item(work_item.work_item_id)
    assert fetched.user_subject == user.sub

    # Verify user_subject field is included in serialization
    serialized = fetched.model_dump()
    assert "user_subject" in serialized
    assert serialized["user_subject"] == user.sub


@pytest.mark.asyncio
async def test_get_work_items_by_ids(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Verify bulk retrieval by IDs in SQLite storage."""
    await storage.upsert_agent(sample_user_id, sample_agent)

    work_items: list[WorkItem] = []
    for _ in range(3):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)
        work_items.append(wi)

    ids = [wi.work_item_id for wi in work_items]
    fetched = await storage.get_work_items_by_ids(ids)

    assert {fi.work_item_id for fi in fetched} == set(ids)


@pytest.mark.asyncio
async def test_list_work_items_filtering(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """List work items for a user with and without agent filter."""
    # Insert two agents
    await storage.upsert_agent(sample_user_id, sample_agent)

    second_agent = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Second Agent",
        },
    )
    await storage.upsert_agent(sample_user_id, second_agent)

    # Create two items for first agent, one for second.
    items = [
        WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            messages=[],
            payload={},
        ),
        WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            messages=[],
            payload={},
        ),
        WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=second_agent.agent_id,
            messages=[],
            payload={},
        ),
    ]
    for wi in items:
        await storage.create_work_item(wi)

    all_items = await storage.list_work_items()
    assert len(all_items) >= 3  # could be more if other tests created items

    by_agent = await storage.list_work_items(agent_id=sample_agent.agent_id)
    # Exactly the two we inserted for first agent should be returned
    ids_first_agent = {items[0].work_item_id, items[1].work_item_id}
    assert ids_first_agent.issubset({wi.work_item_id for wi in by_agent})


async def test_update_work_item_status(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Update status and verify the change persists."""
    await storage.upsert_agent(sample_user_id, sample_agent)

    wi = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,
        messages=[],
        payload={},
    )
    await storage.create_work_item(wi)

    await storage.update_work_item_status(sample_user_id, wi.work_item_id, WorkItemStatus.COMPLETED)

    updated = await storage.get_work_item(wi.work_item_id)
    assert updated is not None
    assert updated.status == WorkItemStatus.COMPLETED


@pytest.mark.asyncio
async def test_work_item_access_control_users(
    storage: SQLiteStorage,
    sample_agent,
):
    """
    Work items owned by the system user are global: any user can read/update/complete them.
    """
    # Create distinct users and the system user
    creator_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    other_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:other")
    system_user, _ = await storage.get_or_create_user("tenant:testing:system:system_user")

    # Agent belongs to the creator, but the work item owner is system_user
    await storage.upsert_agent(creator_user.user_id, sample_agent)

    wi = WorkItem(
        work_item_id=str(uuid4()),
        user_id=system_user.user_id,  # system-owned
        created_by=creator_user.user_id,  # created by a real user
        agent_id=sample_agent.agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
        messages=[],
        initial_messages=[],
        payload={},
    )
    await storage.create_work_item(wi)

    # Other regular user can update status (global visibility for system-owned items)
    await storage.update_work_item_status(
        other_user.user_id, wi.work_item_id, WorkItemStatus.COMPLETED
    )
    updated = await storage.get_work_item(wi.work_item_id)
    assert updated.status == WorkItemStatus.COMPLETED

    # Other regular user can complete and set completed_by
    await storage.complete_work_item(other_user.user_id, wi.work_item_id, WorkItemCompletedBy.HUMAN)
    updated = await storage.get_work_item(wi.work_item_id)
    assert updated.status == WorkItemStatus.COMPLETED
    assert updated.completed_by == WorkItemCompletedBy.HUMAN


@pytest.mark.asyncio
async def test_complete_work_item(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test completing work items with different completed_by values."""
    await storage.upsert_agent(sample_user_id, sample_agent)

    wi = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,
        messages=[],
        payload={},
        completed_by=None,  # Initially not completed
    )
    await storage.create_work_item(wi)

    # Test 1: Complete work item with completed_by=AGENT
    await storage.complete_work_item(
        sample_user_id,
        wi.work_item_id,
        WorkItemCompletedBy.AGENT,
    )

    updated = await storage.get_work_item(wi.work_item_id)
    assert updated is not None
    assert updated.status == WorkItemStatus.COMPLETED
    assert updated.completed_by == WorkItemCompletedBy.AGENT

    # Test 2: Complete work item with completed_by=HUMAN (should overwrite previous completion)
    await storage.complete_work_item(
        sample_user_id,
        wi.work_item_id,
        WorkItemCompletedBy.HUMAN,
    )

    updated = await storage.get_work_item(wi.work_item_id)
    assert updated is not None
    assert updated.status == WorkItemStatus.COMPLETED
    assert updated.completed_by == WorkItemCompletedBy.HUMAN

    # Test 3: Verify that updating status after completion preserves completed_by
    await storage.update_work_item_status(
        sample_user_id,
        wi.work_item_id,
        WorkItemStatus.NEEDS_REVIEW,
    )

    updated = await storage.get_work_item(wi.work_item_id)
    assert updated is not None
    assert updated.status == WorkItemStatus.NEEDS_REVIEW
    assert updated.completed_by == WorkItemCompletedBy.HUMAN  # Should remain unchanged


@pytest.mark.asyncio
async def test_batch_processing_and_mark_error(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test get_work_item_ids_to_process and mark_incomplete_work_items_as_error."""
    await storage.upsert_agent(sample_user_id, sample_agent)

    pending_ids: list[str] = []
    for _ in range(5):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)
        pending_ids.append(wi.work_item_id)

    first_batch = await storage.get_pending_work_item_ids(limit=2)
    assert len(first_batch) == 2

    # Verify they are now EXECUTING
    for wid in first_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.EXECUTING

    second_batch = await storage.get_pending_work_item_ids(limit=10)
    assert len(second_batch) == 3  # Remaining

    # Mark first batch as error (they are still EXECUTING)
    await storage.mark_incomplete_work_items_as_error(first_batch)

    for wid in first_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.ERROR

    # Verify the second batch is still EXECUTING
    for wid in second_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.EXECUTING

    # For completeness, mark remaining as error too
    await storage.mark_incomplete_work_items_as_error(second_batch)
    for wid in second_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.ERROR


@pytest.mark.asyncio
async def test_work_item_file_operations(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test file operations with work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,  # PRECREATED state
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Test get_workitem_files with empty work item
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 0

    # Upload file to work item
    file_id = str(uuid4())
    uploaded_file = await storage.put_file_owner(
        file_id=file_id,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path/document.txt",
        file_ref="document.txt",
        file_hash="test_hash_123",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    assert uploaded_file.file_id == file_id
    assert uploaded_file.file_ref == "document.txt"
    assert uploaded_file.work_item_id == work_item.work_item_id
    assert uploaded_file.thread_id is None
    assert uploaded_file.agent_id is None

    # Test get_workitem_files with file
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 1
    assert files[0].file_id == file_id
    assert files[0].file_ref == "document.txt"

    # Test get_file_by_ref with work item
    file_by_ref = await storage.get_file_by_ref(work_item, "document.txt", sample_user_id)
    assert file_by_ref is not None
    assert file_by_ref.file_id == file_id
    assert file_by_ref.file_ref == "document.txt"


@pytest.mark.asyncio
async def test_work_item_multiple_files_with_different_names(
    storage: SQLiteStorage,
    sample_user_id: str,
):
    """Test that multiple files with different names can be uploaded to work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload first file
    file_id_1 = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id_1,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path1/data1.txt",
        file_ref="data1.txt",
        file_hash="hash1",
        file_size_raw=512,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Upload second file with different name
    file_id_2 = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id_2,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path2/data2.txt",
        file_ref="data2.txt",  # Different name
        file_hash="hash2",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Should have both files
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 2

    file_refs = {f.file_ref for f in files}
    assert file_refs == {"data1.txt", "data2.txt"}

    file_ids = {f.file_id for f in files}
    assert file_ids == {file_id_1, file_id_2}


@pytest.mark.asyncio
async def test_work_item_file_deletion(
    storage: SQLiteStorage,
    sample_user_id: str,
):
    """Test deleting files from work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload file
    file_id = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path/temp.txt",
        file_ref="temp.txt",
        file_hash="temp_hash",
        file_size_raw=256,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Verify file exists
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 1

    # Delete file
    await storage.delete_file(work_item, file_id, sample_user_id)

    # Verify file is deleted
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 0

    # Verify file by ID is also gone
    deleted_file = await storage.get_file_by_id(file_id, sample_user_id)
    assert deleted_file is None


@pytest.mark.asyncio
async def test_associate_work_item_file_success(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
):
    """Test that associate_work_item_file successfully updates file ownership."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create work item initially without thread_id (PRECREATED state)
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,  # Initially no agent
        thread_id=None,  # Initially no thread
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload file to work item (initially without agent_id/thread_id)
    file_id = str(uuid4())
    uploaded_file = await storage.put_file_owner(
        file_id=file_id,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path/document.txt",
        file_ref="document.txt",
        file_hash="test_hash_123",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Verify initial state (no agent_id/thread_id)
    assert uploaded_file.agent_id is None
    assert uploaded_file.thread_id is None
    assert uploaded_file.work_item_id == work_item.work_item_id

    # Create a thread for the work item
    thread = Thread(
        user_id=sample_user_id,
        thread_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(sample_user_id, thread)

    # Associate the file with agent and thread
    await storage.associate_work_item_file(
        file_id=file_id,
        work_item=work_item,
        agent_id=sample_agent.agent_id,
        thread_id=thread.thread_id,
    )

    # Verify file is now associated
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 1
    associated_file = files[0]
    assert associated_file.file_id == file_id
    assert associated_file.agent_id == sample_agent.agent_id
    assert associated_file.thread_id == thread.thread_id
    assert associated_file.work_item_id == work_item.work_item_id


@pytest.mark.asyncio
async def test_associate_work_item_file_updates_existing_entry(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
):
    """Test that associate_work_item_file updates existing entry instead of creating new one."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create work item initially without thread_id (PRECREATED state)
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,  # Initially no agent
        thread_id=None,  # Initially no thread
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload file to work item
    file_id = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id,
        owner=work_item,
        user_id=sample_user_id,
        file_path="/test/path/document.txt",
        file_ref="document.txt",
        file_hash="test_hash_123",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Get initial file count
    files_before = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files_before) == 1

    # Create a thread for the work item
    thread = Thread(
        user_id=sample_user_id,
        thread_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(sample_user_id, thread)

    # Associate the file with agent and thread
    await storage.associate_work_item_file(
        file_id=file_id,
        work_item=work_item,
        agent_id=sample_agent.agent_id,
        thread_id=thread.thread_id,
    )

    # Verify still only one file entry (updated, not duplicated)
    files_after = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files_after) == 1
    assert files_after[0].file_id == file_id
    assert files_after[0].agent_id == sample_agent.agent_id
    assert files_after[0].thread_id == thread.thread_id


@pytest.mark.asyncio
async def test_associate_work_item_file_error_handling(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
):
    """Test error handling in associate_work_item_file."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create work item initially without thread_id (PRECREATED state)
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,  # Initially no agent
        thread_id=None,  # Initially no thread
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Create a thread for the work item
    thread = Thread(
        user_id=sample_user_id,
        thread_id=str(uuid4()),
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await storage.upsert_thread(sample_user_id, thread)

    # Test with non-existent file_id
    non_existent_file_id = str(uuid4())
    with pytest.raises(WorkItemFileNotFoundError):
        await storage.associate_work_item_file(
            file_id=non_existent_file_id,
            work_item=work_item,
            agent_id=sample_agent.agent_id,
            thread_id=thread.thread_id,
        )

    # Upload a file to different work item
    other_work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(other_work_item)

    file_id = str(uuid4())
    await storage.put_file_owner(
        file_id=file_id,
        owner=other_work_item,  # Different work item
        user_id=sample_user_id,
        file_path="/test/path/document.txt",
        file_ref="document.txt",
        file_hash="test_hash_123",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Try to associate with wrong work item - should fail
    with pytest.raises(WorkItemFileNotFoundError):
        await storage.associate_work_item_file(
            file_id=file_id,
            work_item=work_item,  # Wrong work item
            agent_id=sample_agent.agent_id,
            thread_id=thread.thread_id,
        )


@pytest.mark.asyncio
async def test_work_item_file_ownership_system_user(
    storage: SQLiteStorage,
    sample_user_id: str,
):
    """Test that workitem files are owned by system user but accessible to all users."""
    work_items_system_sub = "tenant:work-items:system:system_user"

    # Create system user
    system_user, _ = await storage.get_or_create_user(work_items_system_sub)

    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload file with system user as owner (simulating workitem file upload)
    file_id = str(uuid4())
    uploaded_file = await storage.put_file_owner(
        file_id=file_id,
        owner=work_item,
        user_id=system_user.user_id,  # System user owns the file
        file_path="/test/path/document.txt",
        file_ref="document.txt",
        file_hash="test_hash_123",
        file_size_raw=1024,
        mime_type="text/plain",
        embedded=False,
        embedding_status=None,
        file_path_expiration=None,
    )

    # Verify system user owns the file
    assert uploaded_file.user_id == system_user.user_id

    # System user files should be accessible to all users (per check_user_access logic)
    regular_user_files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(regular_user_files) == 1
    assert regular_user_files[0].file_id == file_id

    # System user should also be able to access the file
    system_user_files = await storage.get_workitem_files(
        work_item.work_item_id, system_user.user_id
    )
    assert len(system_user_files) == 1
    assert system_user_files[0].file_id == file_id


@pytest.mark.asyncio
async def test_get_workitem_files_with_system_user(
    storage: SQLiteStorage,
    sample_user_id: str,
):
    """Test that get_workitem_files works correctly with system user owned files."""
    work_items_system_sub = "tenant:work-items:system:system_user"

    # Create system user
    system_user, _ = await storage.get_or_create_user(work_items_system_sub)

    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Upload multiple files with system user
    file_ids = []
    for i in range(3):
        file_id = str(uuid4())
        file_ids.append(file_id)
        await storage.put_file_owner(
            file_id=file_id,
            owner=work_item,
            user_id=system_user.user_id,
            file_path=f"/test/path/document{i}.txt",
            file_ref=f"document{i}.txt",
            file_hash=f"test_hash_{i}",
            file_size_raw=1024,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )

    # Get files with system user ID
    files = await storage.get_workitem_files(work_item.work_item_id, system_user.user_id)
    assert len(files) == 3

    # Verify all files are returned and owned by system user
    returned_file_ids = {f.file_id for f in files}
    assert returned_file_ids == set(file_ids)
    for file in files:
        assert file.user_id == system_user.user_id
        assert file.work_item_id == work_item.work_item_id

    # Regular user should also be able to access system user files (per check_user_access logic)
    regular_user_files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(regular_user_files) == 3
    for file in regular_user_files:
        assert file.user_id == system_user.user_id  # Still owned by system user
        assert file.work_item_id == work_item.work_item_id


@pytest.mark.asyncio
async def test_update_work_item_all_fields(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test that update_work_item updates all fields including callbacks.

    This test simulates the scenario where a work item is created in PRECREATED state
    (e.g., after file upload) and then updated with all fields when create_work_item
    is called with the existing work_item_id.
    """
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    work_item_id = str(uuid4())

    # Create a work item in PRECREATED state with initial values
    initial_work_item = WorkItem(
        work_item_id=work_item_id,
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=None,
        thread_id=None,
        status=WorkItemStatus.PRECREATED,
        messages=[],  # No messages initially
        payload={},  # Empty payload initially
        callbacks=[],  # No callbacks initially
        completed_by=None,
        status_updated_by=WorkItemStatusUpdatedBy.HUMAN,
    )

    await storage.create_work_item(initial_work_item)

    # Verify initial state
    fetched_initial = await storage.get_work_item(work_item_id)
    assert fetched_initial.status == WorkItemStatus.PRECREATED
    assert fetched_initial.agent_id is None
    assert fetched_initial.messages == []
    assert fetched_initial.payload == {}
    assert fetched_initial.callbacks == []

    # Now update the work item with all new values (simulating create_work_item call)
    updated_work_item = WorkItem(
        work_item_id=work_item_id,
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,  # Now has an agent
        thread_id=None,  # Keep thread_id as None to avoid FK constraint
        status=WorkItemStatus.PENDING,  # New status
        messages=[  # New messages
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Updated message!")],
            ),
        ],
        payload={"updated": "payload", "key": "value"},  # New payload
        callbacks=[  # New callbacks
            WorkItemCallback(
                url="https://example.com/webhook",
                signature_secret="secret123",
                on_status=WorkItemStatus.COMPLETED,
            ),
            WorkItemCallback(
                url="https://example.com/error-webhook",
                on_status=WorkItemStatus.ERROR,
            ),
        ],
        completed_by=WorkItemCompletedBy.HUMAN,  # New completed_by
        status_updated_by=WorkItemStatusUpdatedBy.AGENT,  # New status_updated_by
        created_at=fetched_initial.created_at,  # Keep original created_at
        updated_at=datetime.now(UTC),  # New updated_at
        status_updated_at=datetime.now(UTC),  # New status_updated_at
    )

    # Update the work item
    await storage.update_work_item(updated_work_item)

    # Fetch and verify all fields were updated
    fetched_updated = await storage.get_work_item(work_item_id)

    # Verify core fields
    assert fetched_updated.work_item_id == work_item_id
    assert fetched_updated.user_id == sample_user_id
    assert fetched_updated.agent_id == sample_agent.agent_id
    assert fetched_updated.thread_id is None
    assert fetched_updated.status == WorkItemStatus.PENDING
    assert fetched_updated.completed_by == WorkItemCompletedBy.HUMAN
    assert fetched_updated.status_updated_by == WorkItemStatusUpdatedBy.AGENT

    # Verify messages were updated
    assert len(fetched_updated.messages) == 1
    assert fetched_updated.messages[0].content[0].model_dump()["text"] == "Updated message!"

    # Verify payload was updated
    assert fetched_updated.payload == {"updated": "payload", "key": "value"}

    # Verify callbacks were updated
    assert len(fetched_updated.callbacks) == 2

    # Find callbacks by URL to verify their properties
    callback_by_url = {cb.url: cb for cb in fetched_updated.callbacks}

    assert "https://example.com/webhook" in callback_by_url
    webhook_callback = callback_by_url["https://example.com/webhook"]
    assert webhook_callback.signature_secret == "secret123"
    assert webhook_callback.on_status == WorkItemStatus.COMPLETED

    assert "https://example.com/error-webhook" in callback_by_url
    error_callback = callback_by_url["https://example.com/error-webhook"]
    assert error_callback.signature_secret is None
    assert error_callback.on_status == WorkItemStatus.ERROR

    # Verify that created_at is preserved (not updated)
    assert fetched_updated.created_at == fetched_initial.created_at


@pytest.mark.asyncio
async def test_list_all_work_items_with_system_user(
    storage: SQLiteStorage,
    sample_agent,
):
    """Test that work items created with system user are properly owned by that user."""
    work_items_system_sub = "tenant:work-items:system:system_user"

    # Create system user
    system_user, _ = await storage.get_or_create_user(work_items_system_sub)

    # Ensure the agent exists (FK)
    await storage.upsert_agent(system_user.user_id, sample_agent)

    # Create several work items with system user
    work_item_ids = []
    num_work_items = 5

    for i in range(num_work_items):
        work_item = WorkItem(
            work_item_id=str(uuid4()),
            user_id=system_user.user_id,
            created_by=system_user.user_id,
            agent_id=sample_agent.agent_id,
            thread_id=None,
            status=WorkItemStatus.PENDING,
            messages=[
                ThreadMessage(
                    role="user",
                    content=[ThreadTextContent(text=f"Test message {i}")],
                ),
            ],
            payload={"test_item": i, "system_created": True},
        )
        await storage.create_work_item(work_item)
        work_item_ids.append(work_item.work_item_id)

    # List all work items (no filtering)
    all_work_items = await storage.list_work_items()

    # Verify that we get at least the work items we created
    # (there might be other work items from other tests)
    returned_work_item_ids = {wi.work_item_id for wi in all_work_items}
    created_work_item_ids = set(work_item_ids)

    # All our created work items should be in the returned list
    assert created_work_item_ids.issubset(returned_work_item_ids)

    # Find our created work items in the returned list
    our_work_items = [wi for wi in all_work_items if wi.work_item_id in created_work_item_ids]
    assert len(our_work_items) == num_work_items

    # Verify all returned work items have the same system user ID
    for work_item in our_work_items:
        assert work_item.user_id == system_user.user_id
        assert work_item.created_by == system_user.user_id
        assert work_item.agent_id == sample_agent.agent_id
        assert work_item.status == WorkItemStatus.PENDING

    # Verify payload content for our created items
    payloads = [wi.payload for wi in our_work_items]
    for payload in payloads:
        # Each payload should have system_created=True
        assert payload.get("system_created") is True
        # Each payload should have a unique test_item number
        assert "test_item" in payload

    # Verify we have all expected test_item values
    test_item_values = {payload["test_item"] for payload in payloads}
    expected_values = set(range(num_work_items))
    assert test_item_values == expected_values


@pytest.mark.asyncio
async def test_get_work_items_summary(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test getting work items summary grouped by agent and status."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create work items with different statuses
    work_items = []

    # Create 2 PENDING work items
    for _i in range(2):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)
        work_items.append(wi)

    # Create 1 COMPLETED work item
    wi = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        created_by=sample_user_id,
        agent_id=sample_agent.agent_id,
        status=WorkItemStatus.COMPLETED,
        messages=[],
        payload={},
    )
    await storage.create_work_item(wi)
    work_items.append(wi)

    # Get summary
    summary = await storage.get_work_items_summary(sample_user_id)

    # Should return one agent summary with status counts
    assert len(summary) == 1  # One agent with multiple status counts

    # Group by status to verify counts
    status_counts = {}
    for agent_summary in summary:
        for status, count in agent_summary.work_items_status_counts.items():
            status_counts[status.value] = count

        # Verify row structure
        assert agent_summary.agent_id == sample_agent.agent_id
        assert agent_summary.agent_name == sample_agent.name

    # Verify counts
    assert status_counts["PENDING"] == 2
    assert status_counts["COMPLETED"] == 1


@pytest.mark.asyncio
async def test_get_work_items_summary_empty(
    storage: SQLiteStorage,
    sample_user_id: str,
):
    """Test getting work items summary when user has no work items."""
    summary = await storage.get_work_items_summary(sample_user_id)
    assert summary == []


@pytest.mark.asyncio
async def test_get_work_items_summary_multiple_agents(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test getting work items summary with multiple agents."""
    # Create first agent
    await storage.upsert_agent(sample_user_id, sample_agent)

    # Create second agent
    second_agent = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "name": "Second Agent",
        },
    )
    await storage.upsert_agent(sample_user_id, second_agent)

    # Create work items for first agent
    for _i in range(2):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)

    # Create work items for second agent
    for _i in range(1):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            created_by=sample_user_id,
            agent_id=second_agent.agent_id,
            status=WorkItemStatus.EXECUTING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)

    # Get summary
    summary = await storage.get_work_items_summary(sample_user_id)

    # Should have 2 agent summaries (one for each agent)
    assert len(summary) == 2

    # Group by agent to verify structure
    agent_data = {}
    for agent_summary in summary:
        agent_id = agent_summary.agent_id
        if agent_id not in agent_data:
            agent_data[agent_id] = {}
        for status, count in agent_summary.work_items_status_counts.items():
            agent_data[agent_id][status.value] = count

    # Verify first agent has 2 PENDING work items
    assert sample_agent.agent_id in agent_data
    assert agent_data[sample_agent.agent_id]["PENDING"] == 2

    # Verify second agent has 1 EXECUTING work item
    assert second_agent.agent_id in agent_data
    assert agent_data[second_agent.agent_id]["EXECUTING"] == 1
