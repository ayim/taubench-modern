import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from hashlib import md5
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from agent_platform.core.actions import ActionPackage
from agent_platform.core.agent import (
    Agent,
    AgentArchitecture,
    ObservabilityConfig,
    QuestionGroup,
)
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.runbook import Runbook
from agent_platform.core.thread import Thread, ThreadMessage, ThreadTextContent
from agent_platform.core.utils import SecretString
from agent_platform.server.file_manager import (
    BaseFileManager,
    CloudFileManager,
    FileManagerService,
    InvalidFileUploadError,
    LocalFileManager,
)
from agent_platform.server.storage import (
    PostgresStorage,
    SQLiteStorage,
    UserPermissionError,
)


@pytest.fixture
def mock_requests():
    mock = MagicMock()
    # Mock presigned post response
    mock.post.return_value.status_code = 200
    mock.post.return_value.json.return_value = {
        "url": "https://example.com/upload",
        "form_data": {"key": "value"},
    }
    # Mock presigned get URL response
    mock.get.return_value.status_code = 200
    mock.get.return_value.json.return_value = {
        "url": "https://example.com/download/test-file",
    }
    # Mock file deletion response
    mock.delete.return_value.status_code = 200
    mock.delete.return_value.json.return_value = {"deleted": True}
    # Mock file content download
    mock.get.return_value.content = b"test content"
    return mock


@pytest.fixture(params=["local", "cloud"])
def file_manager(request, mock_requests, storage):
    manager_type = request.param

    # Reset the FileManagerService to ensure a clean state
    FileManagerService.reset()

    if manager_type == "cloud":
        # Set required environment variable
        os.environ["FILE_MANAGEMENT_API_URL"] = "https://example.com/files"
        with patch("agent_platform.server.file_manager.cloud.requests", mock_requests):
            manager = FileManagerService.get_instance(storage, manager_type="cloud")
            yield manager
        # Clean up environment variable
        del os.environ["FILE_MANAGEMENT_API_URL"]
    else:
        manager = FileManagerService.get_instance(storage, manager_type="local")
        yield manager

    # Clean up after the test
    FileManagerService.reset()


@pytest.fixture
def sample_file(tmpdir):
    file_content = b"test content"
    file_path = Path(tmpdir) / "test.txt"
    file_path.write_bytes(file_content)
    with file_path.open("rb") as file_stream:
        yield UploadFile(filename="test.txt", file=file_stream)


@pytest.fixture
def sample_file2(tmpdir):
    file_content = b"updated content"
    file_path = Path(tmpdir) / "test2.txt"
    file_path.write_bytes(file_content)
    with file_path.open("rb") as file_stream:
        yield UploadFile(filename="test2.txt", file=file_stream)


@pytest.fixture(scope="session", params=[pytest.param("", marks=[pytest.mark.postgresql])])
async def postgres_test_db() -> AsyncGenerator[
    dict[str, AsyncConnectionPool[AsyncConnection[tuple[Any, ...]]] | str], None
]:
    """Creates a shared temporary Postgres instance for the entire test session."""
    try:
        # Lazy import testing.postgresql only when needed
        import testing.postgresql

        with testing.postgresql.Postgresql() as postgresql:
            dsn = postgresql.url()
            pool = None
            try:
                pool = AsyncConnectionPool(
                    conninfo=dsn,
                    min_size=2,
                    max_size=50,
                    num_workers=2,
                    open=False,
                    timeout=5,
                    reconnect_timeout=5,
                    max_lifetime=3600,
                    max_idle=300,
                )
                await pool.open()
                yield {
                    "pool": cast(AsyncConnectionPool[AsyncConnection[TupleRow]], pool),
                    "dsn": dsn,
                }
            finally:
                if pool:
                    await pool.close()
                postgresql.stop()
    except (ImportError, RuntimeError):
        # If testing.postgresql is not available, this is expected when running
        # with -m "not postgresql" - the fixture won't be used anyway
        pytest.skip("testing.postgresql is not installed")


@pytest.fixture(
    params=[
        pytest.param("sqlite", marks=[]),
        pytest.param("postgres", marks=[pytest.mark.postgresql]),
    ]
)
async def storage(
    request,
    tmp_path: Path,
    postgres_test_db: dict[str, AsyncConnectionPool[AsyncConnection] | str],
) -> AsyncGenerator[SQLiteStorage | PostgresStorage, None]:
    """
    Parametrized fixture that provides both SQLite and Postgres storage implementations.
    PostgreSQL tests will be skipped,
    but SQLite tests will still run.
    """
    if request.param == "postgres":
        # Pre-truncate: Drop the schema 'v2' if it exists, then recreate it
        match postgres_test_db:
            case {"pool": pool, "dsn": dsn}:
                async with pool.connection() as conn:  # pyright: ignore [reportAttributeAccessIssue]
                    async with conn.cursor() as cur:
                        await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
                        await cur.execute("CREATE SCHEMA v2;")

                storage_instance = PostgresStorage(pool, dsn)  # pyright: ignore [reportArgumentType]
                await storage_instance.setup()
                await storage_instance.get_or_create_user(
                    sub="tenant:testing:system:system_user",
                )
                yield storage_instance
            case _:
                raise ValueError("postgres_test_db fixture is missing pool and dsn")
    else:  # sqlite
        test_file_path = tmp_path / "test_sqlite_storage.db"
        storage_instance = SQLiteStorage(db_path=str(test_file_path))
        if test_file_path.exists():
            test_file_path.unlink()
        await storage_instance.setup()
        await storage_instance.get_or_create_user(
            sub="tenant:testing:system:system_user",
        )
        yield storage_instance
        await storage_instance.teardown()
        if test_file_path.exists():
            test_file_path.unlink()


@pytest.fixture
async def sample_user_id(storage: SQLiteStorage | PostgresStorage) -> str:
    user, created = await storage.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    assert created is False, "User should already exist"
    return user.user_id


@pytest.fixture
def sample_agent(sample_user_id: str) -> Agent:
    return Agent(
        user_id=sample_user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-action-package",
                organization="test-organization",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=["action_1", "action_2"],
            ),
            ActionPackage(
                name="test-action-package-2",
                organization="test-organization-2",
                version="1.0.0",
                url="https://api.test-2.com",
                api_key=SecretString("test-2"),
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default",
            version="1.0.0",
        ),
        question_groups=[
            QuestionGroup(
                title="Test Question Group",
                questions=[
                    "Here's one question",
                    "Here's another question",
                ],
            ),
        ],
        observability_configs=[
            ObservabilityConfig(
                type="langsmith",
                api_key="test",
                api_url="https://api.langsmith.com",
                settings={"some_extra_setting": "some_extra_value"},
            ),
        ],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
    )


@pytest.fixture
def sample_thread(
    sample_agent: Agent,
) -> Thread:
    return Thread(
        thread_id=str(uuid4()),
        user_id=sample_agent.user_id,
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello, how are you?")],
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="I'm fine, thank you!")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"thread_metadata": "some_metadata"},
    )


@pytest.fixture
def sample_uploaded_file(tmpdir, sample_thread: Thread, sample_agent: Agent):
    return UploadedFile(
        file_id=str(uuid4()),
        file_path=os.path.join(str(tmpdir), "test.txt"),
        file_ref="test.txt",
        file_hash="hash",
        file_size_raw=100,
        mime_type="text/plain",
        created_at=datetime.now(UTC),
        user_id=sample_thread.user_id,
        embedded=False,
        file_path_expiration=datetime.now(UTC) + timedelta(hours=1),
        agent_id=sample_agent.agent_id,
        thread_id=sample_thread.thread_id,
    )


@pytest.fixture
async def setup_storage(
    storage: SQLiteStorage | PostgresStorage,
    sample_agent: Agent,
    sample_thread: Thread,
):
    """Setup storage with required user, agent and thread"""
    await storage.get_or_create_user(sub="tenant:testing:system:system_user")
    await storage.upsert_agent(sample_agent.user_id, sample_agent)
    await storage.upsert_thread(sample_agent.user_id, sample_thread)
    return storage


@pytest.fixture
def mock_stream_response():
    """Create a mock for an async HTTP response with streaming capabilities."""
    mock_response = AsyncMock()
    # Create a list to hold chunks that will be returned one by one
    chunks = [b"test", b" chunk", b" content"]

    # Setup mock async iterator for aiter_bytes
    async def async_iter():
        for chunk in chunks:
            yield chunk

    # Assign the async iterator to aiter_bytes
    mock_response.aiter_bytes = async_iter

    return mock_response, b"".join(chunks)


@pytest.mark.asyncio
class TestFileManager:
    @staticmethod
    def get_mock_stream_file_contents():
        """Returns a mock implementation of stream_file_contents
        that yields predefined chunks."""

        async def mock_stream_file_contents(*args, **kwargs):
            # Just yield the chunks directly from our mock
            for chunk in [b"test", b" chunk", b" content"]:
                yield chunk

        return mock_stream_file_contents

    async def test_upload_success(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_uploaded_file: UploadedFile,
    ):
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        assert len(results) == 1
        assert results[0].file_ref == sample_uploaded_file.file_ref
        assert results[0].mime_type == sample_uploaded_file.mime_type
        assert results[0].user_id == sample_uploaded_file.user_id
        assert results[0].thread_id == sample_uploaded_file.thread_id
        assert results[0].agent_id == sample_uploaded_file.agent_id

    async def test_reupload_file(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_uploaded_file: UploadedFile,
    ):
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        assert len(results) == 1
        first_file_id = results[0].file_id
        assert results[0].file_ref == sample_uploaded_file.file_ref
        assert results[0].mime_type == sample_uploaded_file.mime_type
        assert results[0].user_id == sample_uploaded_file.user_id
        assert results[0].thread_id == sample_uploaded_file.thread_id
        assert results[0].agent_id == sample_uploaded_file.agent_id

        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        assert len(results) == 1
        second_file_id = results[0].file_id
        assert first_file_id != second_file_id, "We should use the new file_id after re-upload"
        assert results[0].file_ref == sample_uploaded_file.file_ref
        assert results[0].file_path != sample_uploaded_file.file_path
        assert results[0].file_url == results[0].file_path
        assert results[0].user_id == sample_uploaded_file.user_id
        assert results[0].thread_id == sample_uploaded_file.thread_id
        assert results[0].agent_id == sample_uploaded_file.agent_id

        files = await setup_storage.get_thread_files(sample_thread.thread_id, sample_thread.user_id)
        assert len(files) == 1
        assert files[0].file_id == second_file_id, "Should have fetched the second file"
        assert files[0].file_ref == sample_uploaded_file.file_ref

    async def test_same_file_across_threads(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_uploaded_file: UploadedFile,
    ):
        """Verifies that a file with the same name can be uploaded to multiple threads in the
        same agent.
        """
        # Create a second thread with the same agent.
        thread2 = sample_thread.copy()
        thread2.thread_id = str(uuid4())
        # generate new message IDs in the copied thread
        for msg in thread2.messages:
            msg.message_id = str(uuid4())
        await setup_storage.upsert_thread(sample_thread.user_id, thread2)

        # Upload the same file to both threads.
        for thread in [sample_thread, thread2]:
            results = await file_manager.upload(
                files=[UploadFilePayload(file=sample_file)],
                owner=thread,
                user_id=thread.user_id,
            )

            assert len(results) == 1
            assert results[0].file_ref == sample_uploaded_file.file_ref
            assert results[0].mime_type == sample_uploaded_file.mime_type
            assert results[0].user_id == sample_uploaded_file.user_id
            assert results[0].thread_id == thread.thread_id
            assert results[0].agent_id == sample_uploaded_file.agent_id

    async def test_thread_delete_cleans_up_files(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_uploaded_file: UploadedFile,
    ):
        """Verifies that a file with the same name can be uploaded to multiple threads in the
        same agent.
        """

        # Upload the file to the thread
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        assert len(results) == 1
        assert results[0].file_ref == sample_uploaded_file.file_ref
        assert results[0].mime_type == sample_uploaded_file.mime_type
        assert results[0].user_id == sample_uploaded_file.user_id
        assert results[0].thread_id == sample_thread.thread_id
        assert results[0].agent_id == sample_uploaded_file.agent_id

        # Make sure the file is in the thread
        files = await setup_storage.get_thread_files(
            sample_thread.thread_id,
            sample_thread.user_id,
        )
        assert len(files) == 1
        assert files[0].file_ref == sample_uploaded_file.file_ref
        assert files[0].mime_type == sample_uploaded_file.mime_type
        assert files[0].user_id == sample_uploaded_file.user_id

        # Delete the thread
        await setup_storage.delete_thread(
            sample_thread.user_id,
            sample_thread.thread_id,
        )

        # Make sure the file is deleted
        actual_file = await setup_storage.get_file_by_id(files[0].file_id, sample_thread.user_id)
        assert actual_file is None, (
            "Files should be automatically deleted when the thread is deleted"
        )

    async def test_upload_duplicate_file_names(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_file2: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        with pytest.raises(InvalidFileUploadError, match="File names must be unique"):
            await file_manager.upload(
                files=[
                    UploadFilePayload(file=sample_file),
                    UploadFilePayload(file=sample_file),
                ],
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )

    async def test_upload_invalid_file_names(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        invalid_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", ".", ".."]

        sample_file.filename = ""
        with pytest.raises(InvalidFileUploadError, match="Invalid empty file name"):
            await file_manager.upload(
                files=[UploadFilePayload(file=sample_file)],
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )

        for invalid_name in invalid_names:
            sample_file.filename = invalid_name
            with pytest.raises(InvalidFileUploadError, match="Invalid file name"):
                await file_manager.upload(
                    files=[UploadFilePayload(file=sample_file)],
                    owner=sample_thread,
                    user_id=sample_thread.user_id,
                )

    async def test_upload_invalid_characters(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        invalid_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]

        for char in invalid_chars:
            sample_file.filename = f"test{char}file.txt"
            with pytest.raises(InvalidFileUploadError, match="Invalid file name"):
                await file_manager.upload(
                    files=[UploadFilePayload(file=sample_file)],
                    owner=sample_thread,
                    user_id=sample_thread.user_id,
                )

    async def test_delete_file(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        # Upload a file first
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        file_id = results[0].file_id

        # Delete the file
        await file_manager.delete(
            thread_id=sample_thread.thread_id,
            user_id=sample_thread.user_id,
            file_id=file_id,
        )

        # Verify file is deleted
        file = await setup_storage.get_file_by_id(file_id, sample_thread.user_id)
        assert file is None

    async def test_delete_thread_files(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_file2: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        # Upload multiple files
        await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        await file_manager.upload(
            files=[UploadFilePayload(file=sample_file2)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        # Delete all thread files
        await file_manager.delete_thread_files(
            thread_id=sample_thread.thread_id,
            user_id=sample_thread.user_id,
        )

        files = await setup_storage.get_thread_files(
            sample_thread.user_id,
            sample_thread.thread_id,
        )
        assert len(files) == 0

    async def test_read_file_contents(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        file_id = results[0].file_id

        # Read file contents
        contents = await file_manager.read_file_contents(
            file_id=file_id,
            user_id=sample_thread.user_id,
        )
        await sample_file.seek(0)
        assert contents == await sample_file.read()

    async def test_access_file_wrong_user(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        sample_file: UploadFile,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test accessing a file with wrong user ID."""
        # Upload file with one user
        results = await file_manager.upload(
            files=[UploadFilePayload(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        file_id = results[0].file_id

        # Try to access with different user
        wrong_user_id = str(uuid4())
        with pytest.raises(
            UserPermissionError,
            match="User does not have access to this file",
        ):
            await file_manager.read_file_contents(
                file_id=file_id,
                user_id=wrong_user_id,
            )

    async def test_upload_empty_file_list(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test uploading an empty list of files."""
        with pytest.raises(InvalidFileUploadError, match="Files list cannot be empty"):
            await file_manager.upload(
                files=[],  # Empty list
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )

    async def test_upload_large_file(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test uploading a file that exceeds size limits."""
        # Create a large file
        large_content = BytesIO()
        large_content.write(b"x" * (100 * 1024 * 1024 + 1))  # 100MB + 1 byte
        large_content.seek(0)
        large_file = UploadFile(filename="large.txt", file=large_content)

        # The file manager should handle large files gracefully
        results = await file_manager.upload(
            files=[UploadFilePayload(file=large_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        assert len(results) == 1  # File should be uploaded successfully

    async def test_read_file_contents_nonexistent(
        self,
        file_manager: BaseFileManager,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test reading contents of a non-existent file."""
        nonexistent_file_id = str(uuid4())
        with pytest.raises(Exception, match=f"File not found: {nonexistent_file_id}"):
            await file_manager.read_file_contents(
                file_id=nonexistent_file_id,
                user_id=str(uuid4()),
            )

    async def test_file_mime_type_detection(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test correct MIME type detection for different file types."""
        # Test different file types (txt, pdf, json, etc.)
        file_types = {
            "test.txt": "text/plain",
            "test.pdf": "application/pdf",
            "test.json": "application/json",
        }

        for filename, expected_mime in file_types.items():
            content = b"test content"
            file = UploadFile(filename=filename, file=BytesIO(content))
            results = await file_manager.upload(
                files=[UploadFilePayload(file=file)],
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )
            assert results[0].mime_type == expected_mime

    async def test_download_file_by_ref(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        mock_requests,
        mock_stream_response,
    ):
        """Test downloading a file by reference."""
        # Upload a file first
        content = b"test download content"
        file = UploadFile(filename="test_download.txt", file=BytesIO(content))
        results = await file_manager.upload(
            files=[UploadFilePayload(file=file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        uploaded_file = results[0]

        # Test using stream_file_contents method
        # Collect the chunks to verify content
        chunks = []

        # Test file:// scheme (default for local file manager)
        if isinstance(file_manager, LocalFileManager):
            # Mock Path.open for local file manager
            with (
                patch("pathlib.Path.open", return_value=BytesIO(content)),
                patch(
                    "agent_platform.server.file_manager.utils.url_to_fs_path",
                    return_value=str(Path("/tmp/test_file")),
                ),
            ):
                # Call stream_file_contents directly to test the streaming functionality
                async for chunk in file_manager.stream_file_contents(
                    file_id=uploaded_file.file_id,
                    user_id=sample_thread.user_id,
                ):
                    chunks.append(chunk)

                # Verify the content is correct
                assert b"".join(chunks) == content

        # Test http:// scheme (default for cloud file manager)
        if isinstance(file_manager, CloudFileManager):
            # Setup mocking for httpx streaming
            mock_response, expected_content = mock_stream_response

            # Get the mock implementation of stream_file_contents
            mock_stream_file_contents = self.get_mock_stream_file_contents()

            # Create a new UploadedFile with the desired file_path
            http_mock = UploadedFile(
                file_id=uploaded_file.file_id,
                file_path="http://example.com/test.txt",
                file_ref=uploaded_file.file_ref,
                file_hash=uploaded_file.file_hash,
                file_size_raw=uploaded_file.file_size_raw,
                mime_type=uploaded_file.mime_type,
                created_at=uploaded_file.created_at,
                user_id=uploaded_file.user_id,
                embedded=uploaded_file.embedded,
                file_path_expiration=uploaded_file.file_path_expiration,
                agent_id=uploaded_file.agent_id,
                thread_id=uploaded_file.thread_id,
            )

            # Patch both the file retrieval and the streaming method
            with (
                patch.object(CloudFileManager, "stream_file_contents", mock_stream_file_contents),
                patch(
                    "agent_platform.server.storage.BaseStorage.get_file_by_id",
                    return_value=http_mock,
                ),
            ):
                chunks = []
                async for chunk in file_manager.stream_file_contents(
                    file_id=uploaded_file.file_id,
                    user_id=sample_thread.user_id,
                ):
                    chunks.append(chunk)

                # Verify chunks match expected content
                assert b"".join(chunks) == expected_content

    async def test_download_file_by_ref_not_found(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test downloading a file by reference that doesn't exist."""
        nonexistent_file_id = str(uuid4())

        # Test stream_file_contents with non-existent file ID
        with pytest.raises(Exception, match=f"File not found: {nonexistent_file_id}"):
            async for _ in file_manager.stream_file_contents(
                file_id=nonexistent_file_id,
                user_id=sample_thread.user_id,
            ):
                pass  # We shouldn't reach this point

    async def test_download_file_by_ref_different_schemes(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        mock_requests,
        mock_stream_response,
    ):
        """Test downloading a file with different URL schemes."""
        # Upload a file first
        content = b"test scheme content"
        file = UploadFile(filename="test_scheme.txt", file=BytesIO(content))
        results = await file_manager.upload(
            files=[UploadFilePayload(file=file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        uploaded_file = results[0]

        # Test file:// scheme
        if isinstance(file_manager, LocalFileManager):
            # Create a new UploadedFile with the desired file_path
            file_mock = UploadedFile(
                file_id=uploaded_file.file_id,
                file_path="file:///test/path",
                file_ref=uploaded_file.file_ref,
                file_hash=uploaded_file.file_hash,
                file_size_raw=uploaded_file.file_size_raw,
                mime_type=uploaded_file.mime_type,
                created_at=uploaded_file.created_at,
                user_id=uploaded_file.user_id,
                embedded=uploaded_file.embedded,
                file_path_expiration=uploaded_file.file_path_expiration,
                agent_id=uploaded_file.agent_id,
                thread_id=uploaded_file.thread_id,
            )

            with (
                patch(
                    "agent_platform.server.file_manager.utils.url_to_fs_path",
                    return_value="/test/path",
                ),
                patch("pathlib.Path.open", return_value=BytesIO(content)),
                patch(
                    "agent_platform.server.storage.BaseStorage.get_file_by_id",
                    return_value=file_mock,
                ),
            ):
                chunks = []
                async for chunk in file_manager.stream_file_contents(
                    file_id=uploaded_file.file_id,
                    user_id=sample_thread.user_id,
                ):
                    chunks.append(chunk)

                assert b"".join(chunks) == content

        # Test http:// scheme
        if isinstance(file_manager, CloudFileManager):
            # Setup mocking for httpx streaming
            mock_response, expected_content = mock_stream_response

            # Get the mock implementation of stream_file_contents
            mock_stream_file_contents = self.get_mock_stream_file_contents()

            # Create a new UploadedFile with the desired file_path
            http_mock = UploadedFile(
                file_id=uploaded_file.file_id,
                file_path="http://example.com/test.txt",
                file_ref=uploaded_file.file_ref,
                file_hash=uploaded_file.file_hash,
                file_size_raw=uploaded_file.file_size_raw,
                mime_type=uploaded_file.mime_type,
                created_at=uploaded_file.created_at,
                user_id=uploaded_file.user_id,
                embedded=uploaded_file.embedded,
                file_path_expiration=uploaded_file.file_path_expiration,
                agent_id=uploaded_file.agent_id,
                thread_id=uploaded_file.thread_id,
            )

            # Patch both the file retrieval and the streaming method
            with (
                patch.object(CloudFileManager, "stream_file_contents", mock_stream_file_contents),
                patch(
                    "agent_platform.server.storage.BaseStorage.get_file_by_id",
                    return_value=http_mock,
                ),
            ):
                chunks = []
                async for chunk in file_manager.stream_file_contents(
                    file_id=uploaded_file.file_id,
                    user_id=sample_thread.user_id,
                ):
                    chunks.append(chunk)

                # Verify chunks match expected content
                assert b"".join(chunks) == expected_content

    async def test_request_remote_file_upload(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        sample_agent: Agent,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test requesting remote file upload credentials."""
        # Mock _build_file_url for LocalFileManager
        if isinstance(file_manager, LocalFileManager):
            file_manager._build_file_url = MagicMock(return_value="file:///test/path")

        result = await file_manager.request_remote_file_upload(
            owner=sample_thread,
            file_name="test.txt",
        )

        if isinstance(file_manager, CloudFileManager):
            assert result.url == "https://example.com/upload"
            assert result.form_data == {"key": "value"}
        else:  # LocalFileManager
            assert result.url == "file:///test/path"
            assert result.form_data == {}

        assert result.file_ref == "test.txt"
        assert result.file_id  # Should be a UUID

    async def test_confirm_remote_file_upload(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        mock_requests,
    ):
        """Test confirming a remote file upload."""
        # Clean up any existing files for this thread first
        try:
            await file_manager.delete_thread_files(
                thread_id=sample_thread.thread_id,
                user_id=sample_thread.user_id,
            )
        except Exception:
            pass  # Ignore errors if no files exist

        # Create a unique filename based on the storage and file manager type
        storage_type = "postgres" if isinstance(setup_storage, PostgresStorage) else "sqlite"
        manager_type = "cloud" if isinstance(file_manager, CloudFileManager) else "local"
        unique_filename = f"test_remote_file_{storage_type}_{manager_type}_{uuid4()}.txt"

        # First request the upload
        request_result = await file_manager.request_remote_file_upload(
            owner=sample_thread,
            file_name=unique_filename,
        )

        # Mock _build_file_url for LocalFileManager
        if isinstance(file_manager, LocalFileManager):
            file_manager._build_file_url = MagicMock(return_value="file:///test/path")

        # Then confirm it
        file = await file_manager.confirm_remote_file_upload(
            owner=sample_thread,
            file_ref=request_result.file_ref,
            file_id=request_result.file_id,
        )

        # Verify the file record was created
        assert file.file_id == request_result.file_id
        assert file.file_ref == request_result.file_ref
        assert file.thread_id == sample_thread.thread_id
        assert file.user_id == sample_thread.user_id

        # For cloud implementation, file_path should be a download URL
        if isinstance(file_manager, CloudFileManager):
            # Should be the download URL from the mock's GET response
            expected_download_url = mock_requests.get.return_value.json.return_value["url"]
            assert file.file_path == expected_download_url

        # Verify it's in storage
        stored_file = await setup_storage.get_file_by_id(
            file_id=request_result.file_id,
            user_id=sample_thread.user_id,
        )
        assert stored_file is not None
        assert stored_file.file_id == request_result.file_id

    async def test_request_remote_file_upload_invalid_filename(
        self,
        file_manager: BaseFileManager,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Test requesting remote file upload with invalid filename."""
        # Reserved Windows names
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", ".", "..", ""]
        # Invalid characters
        invalid_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]

        invalid_filenames = [
            *reserved_names,  # Add all reserved Windows names
            *[
                f"test{char}file.txt" for char in invalid_chars
            ],  # Add all invalid character combinations
            "../file.txt",  # Path traversal attempt
            "folder/../file.txt",  # Another path traversal attempt
            "",  # Empty filename
        ]

        for invalid_filename in invalid_filenames:
            with pytest.raises(InvalidFileUploadError, match="Invalid file name"):
                await file_manager.request_remote_file_upload(
                    owner=sample_thread,
                    file_name=invalid_filename,
                )

    async def test_uploaded_file_contains_file_url(
        self,
        sample_uploaded_file: UploadedFile,
    ):
        """Test that UploadedFile includes file_url as an alias for file_path."""
        assert sample_uploaded_file.file_url == sample_uploaded_file.file_path

    async def test_storage_upload_file_same_id(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_agent: Agent,
    ):
        assert sample_file.filename

        file_id = str(uuid4())
        orig_path = "path1"
        file_hash = md5(sample_file.filename.encode()).hexdigest()

        # Upload the file with one ID
        upload1 = await setup_storage.put_file_owner(
            file_id=file_id,
            owner=sample_thread,
            user_id=sample_thread.user_id,
            file_path=orig_path,
            file_ref=sample_file.filename,
            file_hash=file_hash,
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )

        assert upload1.file_id == file_id
        assert upload1.file_path == orig_path
        assert upload1.file_ref == sample_file.filename
        assert upload1.file_hash == md5(sample_file.filename.encode()).hexdigest()
        assert upload1.file_size_raw == 0
        assert upload1.mime_type == "text/plain"
        assert upload1.user_id == sample_thread.user_id
        assert upload1.thread_id == sample_thread.thread_id
        assert upload1.agent_id == sample_agent.agent_id

        # Upload the file with the same ID but different details
        new_path = "path2"
        new_file_hash = md5(sample_file.filename.encode()).hexdigest()
        upload2 = await setup_storage.put_file_owner(
            file_id=file_id,
            owner=sample_thread,
            user_id=sample_thread.user_id,
            file_path=new_path,
            file_ref=sample_file.filename,
            file_hash=new_file_hash,
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )

        # Verify that file_id has not changed but the other details have changed.
        assert upload2.file_id == file_id
        assert upload2.file_path == new_path
        assert upload2.file_ref == sample_file.filename
        assert upload2.file_hash == new_file_hash
        assert upload2.file_size_raw == 0
        assert upload2.mime_type == "text/plain"
        assert upload2.user_id == sample_thread.user_id

    async def test_storage_upload_file_same_ref(
        self,
        file_manager: BaseFileManager,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
        sample_agent: Agent,
    ):
        assert sample_file.filename

        file_id = str(uuid4())
        orig_path = "path1"
        file_hash = md5(sample_file.filename.encode()).hexdigest()

        # Upload the file with one ID
        upload1 = await setup_storage.put_file_owner(
            file_id=file_id,
            owner=sample_thread,
            user_id=sample_thread.user_id,
            file_path=orig_path,
            file_ref=sample_file.filename,
            file_hash=file_hash,
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )

        assert upload1.file_id == file_id
        assert upload1.file_path == orig_path
        assert upload1.file_ref == sample_file.filename
        assert upload1.file_hash == md5(sample_file.filename.encode()).hexdigest()
        assert upload1.file_size_raw == 0
        assert upload1.mime_type == "text/plain"
        assert upload1.user_id == sample_thread.user_id
        assert upload1.thread_id == sample_thread.thread_id
        assert upload1.agent_id == sample_agent.agent_id

        # Upload the file with the same file_ref (name)
        new_file_id = str(uuid4())
        new_path = "path2"
        new_file_hash = md5(sample_file.filename.encode()).hexdigest()
        upload2 = await setup_storage.put_file_owner(
            file_id=new_file_id,
            owner=sample_thread,
            user_id=sample_thread.user_id,
            file_path=new_path,
            file_ref=sample_file.filename,
            file_hash=new_file_hash,
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )

        # Verify that the file_id, file_ref, file_path are updated
        assert upload2.file_id == new_file_id
        assert upload2.file_path == new_path
        assert upload2.file_url == upload2.file_path
        assert upload2.file_ref == sample_file.filename
        assert upload2.file_hash == new_file_hash
        assert upload2.file_size_raw == 0
        assert upload2.mime_type == "text/plain"
        assert upload2.user_id == sample_thread.user_id

    async def test_retrieve_thread_file(
        self,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Verifies that threads which have files of the same name are uniquely returned."""
        assert sample_file.filename

        # Create two threads
        thread1 = sample_thread
        thread2 = thread1.copy()
        thread2.thread_id = str(uuid4())
        thread2.name = "thread2"
        # Copy the messages and update the message_id
        thread2.messages = [msg.copy() for msg in sample_thread.messages]
        for msg in thread2.messages:
            msg.message_id = str(uuid4())

        await setup_storage.upsert_thread(sample_thread.user_id, thread2)

        # Upload file to thread1 with a common name
        file_name = "common.txt"
        file1_id = str(uuid4())
        upload1 = await setup_storage.put_file_owner(
            file_id=file1_id,
            owner=thread1,
            user_id=thread1.user_id,
            file_path=None,
            file_ref=file_name,
            file_hash=md5(file_name.encode()).hexdigest(),
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        assert upload1

        # Upload the file with the same ID but different details
        file2_id = str(uuid4())
        upload2 = await setup_storage.put_file_owner(
            file_id=file2_id,
            owner=thread2,
            user_id=thread2.user_id,
            file_path=None,
            file_ref=file_name,
            file_hash=md5(file_name.encode()).hexdigest(),
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        assert upload2

        # Run a loop multiple times to ensure that we always get the correct file per thread.
        for _ in range(10):
            ref = await setup_storage.get_file_by_ref(thread1, file_name, sample_thread.user_id)
            assert ref
            assert ref.file_id == file1_id

            ref = await setup_storage.get_file_by_ref(thread2, file_name, sample_thread.user_id)
            assert ref
            assert ref.file_id == file2_id

    async def test_delete_thread_file(
        self,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorage | PostgresStorage,
    ):
        """Verifies that threads which have files of the same name are uniquely returned."""
        assert sample_file.filename

        # Create two threads
        thread1 = sample_thread
        thread2 = thread1.copy()
        thread2.thread_id = str(uuid4())
        thread2.name = "thread2"
        # Copy the messages and update the message_id
        thread2.messages = [msg.copy() for msg in sample_thread.messages]
        for msg in thread2.messages:
            msg.message_id = str(uuid4())

        await setup_storage.upsert_thread(sample_thread.user_id, thread2)

        # Upload file to thread1 with a common name
        file_name = "common.txt"
        file1_id = str(uuid4())
        upload1 = await setup_storage.put_file_owner(
            file_id=file1_id,
            owner=thread1,
            user_id=thread1.user_id,
            file_path=None,
            file_ref=file_name,
            file_hash=md5(file_name.encode()).hexdigest(),
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        assert upload1

        # Upload the file with the same ID but different details
        file2_id = str(uuid4())
        upload2 = await setup_storage.put_file_owner(
            file_id=file2_id,
            owner=thread2,
            user_id=thread2.user_id,
            file_path=None,
            file_ref=file_name,
            file_hash=md5(file_name.encode()).hexdigest(),
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        assert upload2

        # Delete the file from the first thread
        await setup_storage.delete_file(thread1, file1_id, thread1.user_id)

        thread1_file = await setup_storage.get_file_by_ref(thread1, file_name, thread1.user_id)
        assert thread1_file is None, "The first thread should no longer have a file"

        thread2_file = await setup_storage.get_file_by_ref(thread2, file_name, thread2.user_id)
        assert thread2_file, "The second thread should still have a file"
        assert thread2_file.file_id == file2_id, "The second thread should still have the same file"


@pytest.mark.asyncio
async def test_upload_files_to_work_item(
    file_manager: BaseFileManager,
    storage: SQLiteStorage | PostgresStorage,
    sample_user_id: str,
):
    """Test uploading multiple files to a work item."""
    # Create a work item
    from uuid import uuid4

    from agent_platform.core.work_items import WorkItem, WorkItemStatus

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
    file1_content = b"First file content"
    file1 = UploadFile(filename="file1.txt", file=BytesIO(file1_content))

    upload_requests = [UploadFilePayload(file=file1)]
    await file_manager.upload(upload_requests, work_item, sample_user_id)

    # Verify first file exists
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 1
    first_file_id = files[0].file_id

    # Upload second file with different name
    file2_content = b"Second file content"
    file2 = UploadFile(filename="file2.txt", file=BytesIO(file2_content))

    upload_requests = [UploadFilePayload(file=file2)]
    await file_manager.upload(upload_requests, work_item, sample_user_id)

    # Verify both files exist
    files = await storage.get_workitem_files(work_item.work_item_id, sample_user_id)
    assert len(files) == 2

    file_refs = {f.file_ref for f in files}
    assert file_refs == {"file1.txt", "file2.txt"}

    file_ids = {f.file_id for f in files}
    assert first_file_id in file_ids  # Original file should still exist


if __name__ == "__main__":
    pytest.main()
