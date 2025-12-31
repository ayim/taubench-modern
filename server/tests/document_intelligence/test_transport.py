"""Tests for DirectKernelTransport.get_file handling of local and remote URLs."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agent_platform.core.files import UploadedFile
from agent_platform.core.thread import Thread
from agent_platform.server.document_intelligence.transport import DirectKernelTransport


def _make_uploaded_file(
    file_id: str | None = None,
    file_path: str | None = "file:///tmp/test.txt",
    file_ref: str = "test.txt",
    thread_id: str | None = None,
    user_id: str | None = None,
) -> UploadedFile:
    """Create a mock UploadedFile for testing."""
    return UploadedFile(
        file_id=file_id or str(uuid4()),
        file_path=file_path,
        file_ref=file_ref,
        file_hash="test-hash",
        file_size_raw=100,
        mime_type="text/plain",
        created_at=datetime.now(UTC),
        thread_id=thread_id,
        user_id=user_id,
    )


def _make_thread(thread_id: str | None = None, user_id: str | None = None) -> Thread:
    """Create a mock Thread for testing."""
    return Thread(
        thread_id=thread_id or str(uuid4()),
        user_id=user_id or str(uuid4()),
        agent_id=str(uuid4()),
        name="Test Thread",
        messages=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_storage():
    """Create a mock storage with common methods."""
    return AsyncMock()


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager with common methods."""
    return AsyncMock()


@pytest.fixture
def mock_server_context():
    """Create a mock server context."""
    return MagicMock()


@pytest.fixture
def transport(mock_storage, mock_file_manager, mock_server_context):
    """Create a DirectKernelTransport instance for testing."""
    return DirectKernelTransport(
        storage=mock_storage,
        file_manager=mock_file_manager,
        thread_id="test-thread-id",
        agent_id="test-agent-id",
        user_id="test-user-id",
        server_context=mock_server_context,
    )


@pytest.mark.asyncio
async def test_get_file_local_file_url(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
    mock_file_manager: AsyncMock,
    tmpdir,
):
    """Test get_file with a local file:// URL returns the local path."""
    # Create an actual temp file
    test_file = Path(tmpdir) / "test.txt"
    test_file.write_text("test content")
    file_url = test_file.as_uri()

    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path=file_url, file_ref="test.txt")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file
    mock_file_manager.refresh_file_paths.return_value = [uploaded_file]

    async with transport.get_file("test.txt") as result:
        assert result == test_file
        mock_storage.get_thread.assert_awaited_once_with("test-user-id", "test-thread-id")
        mock_storage.get_file_by_ref.assert_awaited_once_with(thread, "test.txt", "test-user-id")
        mock_file_manager.refresh_file_paths.assert_awaited_once_with([uploaded_file])


@pytest.mark.asyncio
async def test_get_file_http_url_downloads_to_temp(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
    mock_file_manager: AsyncMock,
):
    """Test get_file with an HTTP URL downloads content to a temp file."""
    http_url = "https://example.com/files/test.pdf"
    file_content = b"PDF file content"

    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path=http_url, file_ref="test.pdf")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file
    mock_file_manager.refresh_file_paths.return_value = [uploaded_file]

    # Mock sema4ai_http.get
    mock_response = MagicMock()
    mock_response.response.data = file_content
    mock_response.raise_for_status = MagicMock()

    with patch("agent_platform.server.document_intelligence.transport.sema4ai_http") as mock_http:
        mock_http.get.return_value = mock_response

        async with transport.get_file("test.pdf") as result:
            # Verify the result is a temp file with correct content
            assert result.exists()
            assert result.suffix == ".pdf"
            assert result.read_bytes() == file_content

            mock_http.get.assert_called_once_with(http_url)

        # Temp file should be cleaned up automatically after context exit


@pytest.mark.asyncio
async def test_get_file_http_url_preserves_extension_from_name(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
    mock_file_manager: AsyncMock,
):
    """Test get_file preserves file extension from name when URL has no extension."""
    # URL without extension (common for presigned S3 URLs)
    http_url = "https://bucket.s3.amazonaws.com/abc123?signature=xyz"
    file_content = b"Excel file content"

    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path=http_url, file_ref="report.xlsx")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file
    mock_file_manager.refresh_file_paths.return_value = [uploaded_file]

    mock_response = MagicMock()
    mock_response.response.data = file_content
    mock_response.raise_for_status = MagicMock()

    with patch("agent_platform.server.document_intelligence.transport.sema4ai_http") as mock_http:
        mock_http.get.return_value = mock_response

        async with transport.get_file("report.xlsx") as result:
            # Should use extension from file name since URL has none
            assert result.suffix == ".xlsx"
            assert result.read_bytes() == file_content

        # Temp file should be cleaned up automatically after context exit


@pytest.mark.asyncio
async def test_get_file_thread_not_found(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
):
    """Test get_file raises FileNotFoundError when thread doesn't exist."""
    mock_storage.get_thread.return_value = None

    with pytest.raises(FileNotFoundError, match="Thread test-thread-id not found"):
        async with transport.get_file("test.txt"):
            pass


@pytest.mark.asyncio
async def test_get_file_file_not_found(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
):
    """Test get_file raises FileNotFoundError when file doesn't exist in thread."""
    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = None

    with pytest.raises(FileNotFoundError, match="File test.txt not found in thread"):
        async with transport.get_file("test.txt"):
            pass


@pytest.mark.asyncio
async def test_get_file_no_file_path(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
):
    """Test get_file raises FileNotFoundError when file has no file_path."""
    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path=None, file_ref="test.txt")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file

    with pytest.raises(FileNotFoundError, match="File test.txt has no file_path"):
        async with transport.get_file("test.txt"):
            pass


@pytest.mark.asyncio
async def test_get_file_refresh_fails(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
    mock_file_manager: AsyncMock,
):
    """Test get_file raises FileNotFoundError when refresh returns no results."""
    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path="file:///tmp/test.txt", file_ref="test.txt")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file
    mock_file_manager.refresh_file_paths.return_value = []

    with pytest.raises(FileNotFoundError, match="File test.txt path not available after refresh"):
        async with transport.get_file("test.txt"):
            pass


@pytest.mark.asyncio
async def test_get_file_http_download_fails(
    transport: DirectKernelTransport,
    mock_storage: AsyncMock,
    mock_file_manager: AsyncMock,
):
    """Test get_file raises FileNotFoundError when HTTP download fails."""
    http_url = "https://example.com/files/test.pdf"

    thread = _make_thread(thread_id="test-thread-id", user_id="test-user-id")
    uploaded_file = _make_uploaded_file(file_path=http_url, file_ref="test.pdf")

    mock_storage.get_thread.return_value = thread
    mock_storage.get_file_by_ref.return_value = uploaded_file
    mock_file_manager.refresh_file_paths.return_value = [uploaded_file]

    with patch("agent_platform.server.document_intelligence.transport.sema4ai_http") as mock_http:
        mock_http.get.side_effect = Exception("Connection refused")

        with pytest.raises(FileNotFoundError, match="Failed to download file test.pdf"):
            async with transport.get_file("test.pdf"):
                pass
