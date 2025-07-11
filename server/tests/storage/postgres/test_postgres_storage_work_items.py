from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage.errors import WorkItemFileNotFoundError
from agent_platform.server.storage.postgres import PostgresStorage


@pytest.mark.asyncio
async def test_create_and_get_work_item(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent,
):
    """Create a work item and retrieve it back from Postgres storage."""
    # Ensure the agent exists (FK)
    await storage.upsert_agent(sample_user_id, sample_agent)

    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
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
    assert len(fetched.messages) == 1
    assert fetched.messages[0].content[0].model_dump()["text"] == "Hello!"


@pytest.mark.asyncio
async def test_get_work_items_by_ids(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent,
):
    """Verify bulk retrieval by IDs in Postgres storage."""
    await storage.upsert_agent(sample_user_id, sample_agent)

    items: list[WorkItem] = []
    for _ in range(3):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)
        items.append(wi)

    ids = [wi.work_item_id for wi in items]
    fetched = await storage.get_work_items_by_ids(ids)
    assert {fi.work_item_id for fi in fetched} == set(ids)


@pytest.mark.asyncio
async def test_list_work_items_filtering(
    storage: PostgresStorage,
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
            agent_id=sample_agent.agent_id,
            messages=[],
            payload={},
        ),
        WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=sample_agent.agent_id,
            messages=[],
            payload={},
        ),
        WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=second_agent.agent_id,
            messages=[],
            payload={},
        ),
    ]
    for wi in items:
        await storage.create_work_item(wi)

    all_items = await storage.list_work_items(sample_user_id)
    assert len(all_items) >= 3

    by_agent = await storage.list_work_items(sample_user_id, agent_id=sample_agent.agent_id)
    ids_first_agent = {items[0].work_item_id, items[1].work_item_id}
    assert ids_first_agent.issubset({wi.work_item_id for wi in by_agent})


@pytest.mark.asyncio
async def test_update_work_item_status(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent,
):
    await storage.upsert_agent(sample_user_id, sample_agent)

    wi = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
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
async def test_batch_processing_and_mark_error(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent,
):
    await storage.upsert_agent(sample_user_id, sample_agent)

    pending_ids: list[str] = []
    for _ in range(5):
        wi = WorkItem(
            work_item_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=sample_agent.agent_id,
            status=WorkItemStatus.PENDING,
            messages=[],
            payload={},
        )
        await storage.create_work_item(wi)
        pending_ids.append(wi.work_item_id)

    first_batch = await storage.get_pending_work_item_ids(limit=2)
    assert len(first_batch) == 2

    for wid in first_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.EXECUTING

    second_batch = await storage.get_pending_work_item_ids(limit=10)
    assert len(second_batch) == 3

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

    await storage.mark_incomplete_work_items_as_error(second_batch)
    for wid in second_batch:
        item = await storage.get_work_item(wid)
        assert item is not None
        assert item.status == WorkItemStatus.ERROR


@pytest.mark.asyncio
async def test_work_item_file_operations(
    storage: PostgresStorage,
    sample_user_id: str,
    sample_agent,
):
    """Test file operations with work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
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
    storage: PostgresStorage,
    sample_user_id: str,
):
    """Test that multiple files with different names can be uploaded to work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
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
    storage: PostgresStorage,
    sample_user_id: str,
):
    """Test deleting files from work items."""
    # Create work item
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=sample_user_id,
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
    storage: PostgresStorage,
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
    storage: PostgresStorage,
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
    storage: PostgresStorage,
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
    storage: PostgresStorage,
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
    storage: PostgresStorage,
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
