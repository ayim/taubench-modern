import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import testing.postgresql
from fastapi import UploadFile
from psycopg_pool import AsyncConnectionPool

from agent_server_types_v2.actions import ActionPackage
from agent_server_types_v2.agent import (
    Agent,
    AgentArchitecture,
    ObservabilityConfig,
    QuestionGroup,
)
from agent_server_types_v2.files import UploadedFile, UploadFileRequest
from agent_server_types_v2.runbook import Runbook
from agent_server_types_v2.thread import Thread, ThreadMessage, ThreadTextContent
from sema4ai_agent_server.file_manager.v2.base_v2 import (
    BaseFileManagerV2,
    InvalidFileUploadError,
)
from sema4ai_agent_server.file_manager.v2.cloud_v2 import CloudFileManagerV2
from sema4ai_agent_server.file_manager.v2.local_v2 import LocalFileManagerV2
from sema4ai_agent_server.storage.v2.errors_v2 import (
    ThreadFileNotFoundError,
    UserPermissionError,
)
from sema4ai_agent_server.storage.v2.postgres_v2 import PostgresStorageV2
from sema4ai_agent_server.storage.v2.sqlite_v2 import SQLiteStorageV2


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


@pytest.fixture(params=[LocalFileManagerV2, CloudFileManagerV2])
def file_manager(request, mock_requests):
    manager_class = request.param
    manager = manager_class()

    if isinstance(manager, CloudFileManagerV2):
        # Mock cloud file manager specific methods
        patch_target = "sema4ai_agent_server.file_manager.v2.cloud_v2.requests"
        # Set required environment variable
        os.environ["FILE_MANAGEMENT_API_URL"] = "https://example.com/files"
        with patch(patch_target, mock_requests):
            yield manager
        # Clean up environment variable
        del os.environ["FILE_MANAGEMENT_API_URL"]
    else:
        yield manager


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


@pytest.fixture(scope="session")
async def postgres_test_db() -> AsyncGenerator[AsyncConnectionPool, None]:
    """Creates a shared temporary Postgres instance for the entire test session."""
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
            yield pool
        finally:
            if pool:
                await pool.close()
            postgresql.stop()


@pytest.fixture(params=["sqlite", "postgres"])
async def storage(
    request,
    tmp_path: Path,
    postgres_test_db: AsyncConnectionPool,
) -> AsyncGenerator[SQLiteStorageV2 | PostgresStorageV2, None]:
    """
    Parametrized fixture that provides both SQLite and Postgres storage implementations.
    """
    if request.param == "postgres":
        # Pre-truncate: Drop the schema 'v2' if it exists, then recreate it
        async with postgres_test_db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP SCHEMA IF EXISTS v2 CASCADE;")
                await cur.execute("CREATE SCHEMA v2;")

        storage_instance = PostgresStorageV2(postgres_test_db)
        await storage_instance.setup_v2()
        await storage_instance.get_or_create_user_v2(
            sub="tenant:testing:system:system_user",
        )
        yield storage_instance
    else:  # sqlite
        test_file_path = tmp_path / "test_sqlite_storage.db"
        storage_instance = SQLiteStorageV2(db_path=str(test_file_path))
        if test_file_path.exists():
            test_file_path.unlink()
        await storage_instance.setup_v2()
        await storage_instance.get_or_create_user_v2(
            sub="tenant:testing:system:system_user",
        )
        yield storage_instance
        await storage_instance.teardown_v2()
        if test_file_path.exists():
            test_file_path.unlink()


@pytest.fixture
async def sample_user_id(storage: SQLiteStorageV2 | PostgresStorageV2) -> str:
    user, created = await storage.get_or_create_user_v2(
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
        runbook=Runbook(
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
                api_key="test",
                allowed_actions=["action_1", "action_2"],
            ),
            ActionPackage(
                name="test-action-package-2",
                organization="test-organization-2",
                version="1.0.0",
                url="https://api.test-2.com",
                api_key="test-2",
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
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
        provider_configs=["test-provider-config"],
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
    storage: SQLiteStorageV2 | PostgresStorageV2,
    sample_agent: Agent,
    sample_thread: Thread,
):
    """Setup storage with required user, agent and thread"""
    await storage.get_or_create_user_v2(sub="tenant:testing:system:system_user")
    await storage.upsert_agent_v2(sample_agent.user_id, sample_agent)
    await storage.upsert_thread_v2(sample_agent.user_id, sample_thread)
    return storage


@pytest.mark.asyncio
@patch("sema4ai_agent_server.file_manager.v2.local_v2.get_storage_v2")
@patch("sema4ai_agent_server.file_manager.v2.cloud_v2.get_storage_v2")
class TestFileManager:
    async def test_upload_success(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
        sample_uploaded_file: UploadedFile,
    ):
        # Set up both mocks to return the same storage
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        results = await file_manager.upload(
            files=[UploadFileRequest(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        assert len(results) == 1
        assert results[0].file_ref == sample_uploaded_file.file_ref
        assert results[0].mime_type == sample_uploaded_file.mime_type
        assert results[0].user_id == sample_uploaded_file.user_id
        assert results[0].thread_id == sample_uploaded_file.thread_id
        assert results[0].agent_id == sample_uploaded_file.agent_id

    async def test_upload_duplicate_file_names(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_file2: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        with pytest.raises(InvalidFileUploadError, match="File names must be unique"):
            await file_manager.upload(
                files=[
                    UploadFileRequest(file=sample_file),
                    UploadFileRequest(file=sample_file),
                ],
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )

    async def test_upload_invalid_file_names(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage
        invalid_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", ".", "..", ""]

        for invalid_name in invalid_names:
            sample_file.filename = invalid_name
            with pytest.raises(InvalidFileUploadError, match="Invalid file name"):
                await file_manager.upload(
                    files=[UploadFileRequest(file=sample_file)],
                    owner=sample_thread,
                    user_id=sample_thread.user_id,
                )

    async def test_upload_invalid_characters(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage
        invalid_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]

        for char in invalid_chars:
            sample_file.filename = f"test{char}file.txt"
            with pytest.raises(InvalidFileUploadError, match="Invalid file name"):
                await file_manager.upload(
                    files=[UploadFileRequest(file=sample_file)],
                    owner=sample_thread,
                    user_id=sample_thread.user_id,
                )

    async def test_delete_file(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        # Upload a file first
        results = await file_manager.upload(
            files=[UploadFileRequest(file=sample_file)],
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
        file = await setup_storage.get_file_by_id_v2(file_id, sample_thread.user_id)
        assert file is None

    async def test_delete_thread_files(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_file2: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        # Upload multiple files
        await file_manager.upload(
            files=[UploadFileRequest(file=sample_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        await file_manager.upload(
            files=[UploadFileRequest(file=sample_file2)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )

        # Delete all thread files
        await file_manager.delete_thread_files(
            thread_id=sample_thread.thread_id,
            user_id=sample_thread.user_id,
        )

        # Verify files are deleted
        with pytest.raises(ThreadFileNotFoundError):
            await setup_storage.get_thread_files_v2(
                sample_thread.user_id,
                sample_thread.thread_id,
            )

    async def test_read_file_contents(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_file: UploadFile,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2,
    ):
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage
        results = await file_manager.upload(
            files=[UploadFileRequest(file=sample_file)],
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
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_thread: Thread,
        sample_file: UploadFile,
        setup_storage: SQLiteStorageV2 | PostgresStorageV2,
    ):
        """Test accessing a file with wrong user ID."""
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        # Upload file with one user
        results = await file_manager.upload(
            files=[UploadFileRequest(file=sample_file)],
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
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2 | PostgresStorageV2,
    ):
        """Test uploading an empty list of files."""
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        with pytest.raises(InvalidFileUploadError, match="Files list cannot be empty"):
            await file_manager.upload(
                files=[],  # Empty list
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )

    async def test_upload_large_file(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2 | PostgresStorageV2,
    ):
        """Test uploading a file that exceeds size limits."""
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        # Create a large file
        large_content = BytesIO()
        large_content.write(b"x" * (100 * 1024 * 1024 + 1))  # 100MB + 1 byte
        large_content.seek(0)
        large_file = UploadFile(filename="large.txt", file=large_content)

        # The file manager should handle large files gracefully
        results = await file_manager.upload(
            files=[UploadFileRequest(file=large_file)],
            owner=sample_thread,
            user_id=sample_thread.user_id,
        )
        assert len(results) == 1  # File should be uploaded successfully

    async def test_read_file_contents_nonexistent(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        setup_storage: SQLiteStorageV2 | PostgresStorageV2,
    ):
        """Test reading contents of a non-existent file."""
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

        nonexistent_file_id = str(uuid4())
        with pytest.raises(Exception, match=f"File not found: {nonexistent_file_id}"):
            await file_manager.read_file_contents(
                file_id=nonexistent_file_id,
                user_id=str(uuid4()),
            )

    async def test_file_mime_type_detection(
        self,
        mock_get_storage_cloud,
        mock_get_storage_local,
        file_manager: BaseFileManagerV2,
        sample_thread: Thread,
        setup_storage: SQLiteStorageV2 | PostgresStorageV2,
    ):
        """Test correct MIME type detection for different file types."""
        mock_get_storage_cloud.return_value = setup_storage
        mock_get_storage_local.return_value = setup_storage

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
                files=[UploadFileRequest(file=file)],
                owner=sample_thread,
                user_id=sample_thread.user_id,
            )
            assert results[0].mime_type == expected_mime


if __name__ == "__main__":
    pytest.main()
