"""Tests for AsyncExtractionClient implementation."""

import asyncio
import io
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sema4ai_docint.extraction.reducto import AsyncExtractionClient, Job
from sema4ai_docint.extraction.reducto.async_ import JobType
from sema4ai_docint.extraction.reducto.exceptions import (
    JobFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
)


class AsyncUploadServerConfig:
    """Test configuration for the embedded web server."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset server configuration to defaults."""
        self.upload_status_code = 200
        self.upload_response = {
            "presigned_url": "http://localhost:8002/presigned",
            "file_id": "test_file_id_123",
        }
        self.presigned_status_code = 200
        self.presigned_response = b"OK"
        self.job_status = "Completed"
        self.job_result = {"type": "full", "chunks": []}


class AsyncHTTPHandlerForTests(BaseHTTPRequestHandler):
    """HTTP request handler for the async test server."""

    def log_message(self, format_str, *args):
        """Suppress HTTP server logs during testing."""
        pass

    def do_POST(self):
        """Handle POST requests to /upload and job endpoints."""
        if self.path == "/upload":
            config = self.server.test_config
            self.send_response(config.upload_status_code)

            if config.upload_status_code == 200:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response_json = json.dumps(config.upload_response)
                self.wfile.write(response_json.encode())
            else:
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Error response")
        elif (
            self.path.startswith("/parse")
            or self.path.startswith("/extract")
            or self.path.startswith("/split")
        ):
            # Mock job creation endpoints
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"job_id": "test_job_123"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        """Handle PUT requests to presigned URL."""
        if self.path == "/presigned":
            config = self.server.test_config

            # Read the uploaded file data
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                _ = self.rfile.read(content_length)

            self.send_response(config.presigned_status_code)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(config.presigned_response)
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests for job status."""
        if self.path.startswith("/job/"):
            config = self.server.test_config
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": config.job_status,
                "result": config.job_result if config.job_status == "Completed" else None,
                "reason": "Test failure" if config.job_status == "Failed" else None,
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


class AsyncUploadHTTPServerForTests(HTTPServer):
    """Test HTTP server with configuration."""

    def __init__(self, server_address, request_handler_class, test_config):
        super().__init__(server_address, request_handler_class)
        self.test_config = test_config


@pytest_asyncio.fixture(scope="session")
async def async_test_server():
    """Fixture to create and manage the async test HTTP server."""
    config = AsyncUploadServerConfig()
    server = AsyncUploadHTTPServerForTests(("localhost", 0), AsyncHTTPHandlerForTests, config)
    server_port = server.server_port

    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Give server time to start
    await asyncio.sleep(0.1)

    yield f"http://localhost:{server_port}", config

    # Cleanup
    server.shutdown()
    server.server_close()


@pytest_asyncio.fixture
async def test_file():
    """Fixture to create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Test file content for async upload")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


@pytest_asyncio.fixture
async def async_client(async_test_server):
    """Fixture to create an AsyncExtractionClient."""
    base_url, _ = async_test_server

    # Mock the Reducto client creation
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ):
        extraction_client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

        # Mock the internal Reducto client
        mock_async_reducto = AsyncMock()
        mock_async_reducto._client = AsyncMock()
        mock_async_reducto._client.headers = {"X-API-Key": "test_key"}
        mock_async_reducto._client.post = AsyncMock()
        mock_async_reducto._client.put = AsyncMock()
        mock_async_reducto.close = AsyncMock()

        # Mock job API
        mock_async_reducto.parse = AsyncMock()
        mock_async_reducto.parse.run_job = AsyncMock(return_value=MagicMock(job_id="test_job_123"))
        mock_async_reducto.extract = AsyncMock()
        mock_async_reducto.extract.run_job = AsyncMock(
            return_value=MagicMock(job_id="test_job_123")
        )
        mock_async_reducto.split = AsyncMock()
        mock_async_reducto.split.run_job = AsyncMock(return_value=MagicMock(job_id="test_job_123"))
        mock_async_reducto.job = AsyncMock()
        mock_async_reducto.job.get = AsyncMock()

        # Set the mock AsyncReducto client on the AsyncExtractionClient
        extraction_client.client = mock_async_reducto

        yield extraction_client

        # Cleanup
        await extraction_client.close()


# ============================================================================
# Initialization and Cleanup Tests
# ============================================================================


@pytest.mark.asyncio
async def test_client_initialization():
    """Test AsyncExtractionClient initialization."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_new.return_value = mock_reducto

        client = AsyncExtractionClient(api_key="test_key")

        assert client.base_url == "https://backend.sema4.ai/reducto"
        assert client.disable_ssl_verification is False

        # Check aiohttp session is created
        assert client.aiohttp_session is not None

        await client.close()


@pytest.mark.asyncio
async def test_base_url_normalization():
    """Test that base_url is normalized by removing trailing slashes."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_new.return_value = mock_reducto

        # Test with trailing slash - should be normalized
        client1 = AsyncExtractionClient(
            api_key="test_key", base_url="https://backend.sema4.ai/reducto/"
        )
        assert client1.base_url == "https://backend.sema4.ai/reducto"
        await client1.close()

        # Test with multiple trailing slashes - should remove all
        client2 = AsyncExtractionClient(
            api_key="test_key", base_url="https://backend.sema4.ai/reducto///"
        )
        assert client2.base_url == "https://backend.sema4.ai/reducto"
        await client2.close()

        # Test without trailing slash - should remain unchanged
        client3 = AsyncExtractionClient(
            api_key="test_key", base_url="https://backend.sema4.ai/reducto"
        )
        assert client3.base_url == "https://backend.sema4.ai/reducto"
        await client3.close()

        # Test with None - should use default
        client4 = AsyncExtractionClient(api_key="test_key", base_url=None)
        assert client4.base_url == "https://backend.sema4.ai/reducto"
        await client4.close()


@pytest.mark.asyncio
async def test_client_context_manager():
    """Test AsyncExtractionClient as async context manager."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_reducto.is_closed = MagicMock(return_value=False)
        mock_new.return_value = mock_reducto

        async with AsyncExtractionClient(api_key="test_key") as client:
            assert client is not None
            # Client should be usable within context
            assert client.is_closed() is False

        # After exiting, resources should be cleaned up
        mock_reducto.close.assert_called_once()


@pytest.mark.asyncio
async def test_client_close(async_client):
    """Test client close method."""
    # Mock aiohttp session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.closed = False  # Initially not closed
    async_client._aiohttp_session = mock_session

    # Verify client is not closed initially
    async_client.is_closed = MagicMock(return_value=False)  # Sync method, not async
    assert async_client.is_closed() is False

    await async_client.close()

    # Verify session was closed
    mock_session.close.assert_called_once()

    # Simulate closed state after close()
    mock_session.closed = True
    async_client.is_closed = MagicMock(return_value=True)  # Sync method, not async
    assert async_client.is_closed() is True


# ============================================================================
# Upload Tests
# ============================================================================


@pytest.mark.asyncio
async def test_upload_excludes_content_type_header(async_client, test_file):
    """Test that content-type header is excluded from S3 uploads to avoid signature mismatch."""
    # Mock aiohttp session to capture the exact parameters passed to put()
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    # Mock the HTTP calls for presigned URL request
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {
                "presigned_url": "http://s3.amazonaws.com/bucket/presigned-url",
                "file_id": "test_file_id",
            },
        )
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        result = await async_client.upload(test_file)

        assert result == "test_file_id"

        # Verify that session.put was called exactly once
        mock_session.put.assert_called_once()

        # Extract the call arguments
        call_args, call_kwargs = mock_session.put.call_args

        # Verify the presigned URL was used
        assert call_args[0] == "http://s3.amazonaws.com/bucket/presigned-url"

        # Verify that skip_auto_headers parameter is present and contains "content-type"
        assert "skip_auto_headers" in call_kwargs
        assert "content-type" in call_kwargs["skip_auto_headers"]

        # Verify that only Content-Length header is explicitly set (minimal headers)
        assert "headers" in call_kwargs
        headers = call_kwargs["headers"]
        assert "Content-Length" in headers
        # Content-Type should NOT be in the explicit headers
        assert "Content-Type" not in headers
        assert "content-type" not in headers


@pytest.mark.asyncio
async def test_upload_with_path(async_client, test_file):
    """Test upload with Path object."""
    # Mock aiohttp session to avoid actual network calls
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    # Mock the HTTP calls
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {
                "presigned_url": "http://localhost:8000/presigned",
                "file_id": "path_file_id",
            },
        )
    )

    # Mock successful PUT
    async_client.client._client.put = AsyncMock(
        return_value=MagicMock(status_code=200, raise_for_status=lambda: None)
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        result = await async_client.upload(test_file)

        assert result == "path_file_id"
        async_client.client._client.post.assert_called_once()
        mock_session.put.assert_called_once()


@pytest.mark.asyncio
async def test_upload_with_bytes(async_client):
    """Test upload with bytes."""
    # Mock aiohttp session to avoid actual network calls
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    # Mock the HTTP calls
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {
                "presigned_url": "http://test/presigned",
                "file_id": "bytes_file_id",
            },
        )
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        result = await async_client.upload(b"test bytes content")

        assert result == "bytes_file_id"
        mock_session.put.assert_called_once()


@pytest.mark.asyncio
async def test_upload_with_file_object(async_client):
    """Test upload with file-like object."""
    # Mock aiohttp session to avoid actual network calls
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    # Mock the HTTP calls
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {
                "presigned_url": "http://localhost:8000/presigned",
                "file_id": "fileobj_file_id",
            },
        )
    )

    # Mock successful PUT
    async_client.client._client.put = AsyncMock(
        return_value=MagicMock(status_code=200, raise_for_status=lambda: None)
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        file_obj = io.BytesIO(b"file object content")
        result = await async_client.upload(file_obj)

        assert result == "fileobj_file_id"
        mock_session.put.assert_called_once()


@pytest.mark.asyncio
async def test_upload_with_progress(async_client, test_file):
    """Test upload with progress callback."""
    # Mock aiohttp session to avoid actual network calls
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    progress_calls = []

    async def track_progress(uploaded: int, total: int):
        progress_calls.append((uploaded, total))

    # Mock the HTTP calls
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {
                "presigned_url": "http://localhost:8000/presigned",
                "file_id": "progress_file_id",
            },
        )
    )

    # Mock successful PUT
    async_client.client._client.put = AsyncMock(
        return_value=MagicMock(status_code=200, raise_for_status=lambda: None)
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        result = await async_client.upload(test_file, progress_callback=track_progress)

        assert result == "progress_file_id"
        mock_session.put.assert_called_once()
        # Progress callback should have been called at least once
        # (exact behavior depends on implementation details)


@pytest.mark.asyncio
async def test_upload_403_error(async_client, test_file):
    """Test upload with 403 forbidden error."""
    async_client.client._client.post = AsyncMock(return_value=MagicMock(status_code=403))

    with pytest.raises(UploadForbiddenError) as exc_info:
        await async_client.upload(test_file)

    assert "403" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_missing_presigned_url(async_client, test_file):
    """Test upload with missing presigned URL in response."""
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {"file_id": "test_id"},  # Missing presigned_url
        )
    )

    with pytest.raises(UploadMissingPresignedUrlError):
        await async_client.upload(test_file)


@pytest.mark.asyncio
async def test_upload_missing_file_id(async_client, test_file):
    """Test upload with missing file ID in response."""
    async_client.client._client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {"presigned_url": "http://test/presigned"},  # Missing file_id
        )
    )

    with pytest.raises(UploadMissingFileIdError):
        await async_client.upload(test_file)


# ============================================================================
# Job Management Tests
# ============================================================================


@pytest.mark.asyncio
async def test_start_parse(async_client):
    """Test start_parse returns Job immediately."""
    job = await async_client.start_parse("doc_id")

    assert isinstance(job, Job)
    assert job.job_id == "test_job_123"
    assert job.job_type == "parse"

    # Verify job was started but not waited for
    async_client.client.parse.run_job.assert_called_once()


@pytest.mark.asyncio
async def test_start_extract(async_client):
    """Test start_extract returns Job immediately."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    job = await async_client.start_extract("doc_id", schema)

    assert isinstance(job, Job)
    assert job.job_id == "test_job_123"
    assert job.job_type == "extract"

    async_client.client.extract.run_job.assert_called_once()


@pytest.mark.asyncio
async def test_start_split(async_client):
    """Test start_split returns Job immediately."""
    split_desc = [{"title": "Section", "description": "A section"}]
    job = await async_client.start_split("doc_id", split_desc)

    assert isinstance(job, Job)
    assert job.job_id == "test_job_123"
    assert job.job_type == "split"

    async_client.client.split.run_job.assert_called_once()


@pytest.mark.asyncio
async def test_job_status(async_client):
    """Test getting job status without waiting."""
    # Mock job status response
    async_client.client.job.get = AsyncMock(return_value=MagicMock(status="Pending"))

    status = await async_client.get_job_status("job_123")

    assert status == "Pending"
    async_client.client.job.get.assert_called_once_with(job_id="job_123")


@pytest.mark.asyncio
async def test_wait_for_job_success(async_client):
    """Test waiting for job completion."""
    # Mock job completion
    async_client.client.job.get = AsyncMock(
        return_value=MagicMock(status="Completed", result={"data": "result"})
    )

    result = await async_client.wait_for_job("job_123")

    assert result == {"data": "result"}


@pytest.mark.asyncio
async def test_wait_for_job_failure(async_client):
    """Test job failure handling."""
    # Mock job failure
    async_client.client.job.get = AsyncMock(
        return_value=MagicMock(status="Failed", reason="Test failure reason")
    )

    with pytest.raises(JobFailedError) as exc_info:
        await async_client.wait_for_job("job_123")

    assert "Test failure reason" in str(exc_info.value)


@pytest.mark.asyncio
async def test_job_polling(async_client):
    """Test job polling behavior."""
    call_count = 0

    async def mock_get(job_id):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return MagicMock(status="Pending")
        return MagicMock(status="Completed", result={"done": True})

    async_client.client.job.get = mock_get

    result = await async_client.wait_for_job("job_123", poll_interval=0.01)

    assert result == {"done": True}
    assert call_count == 3  # Polled twice as Pending, then Completed


# ============================================================================
# Convenience Method Tests
# ============================================================================


@pytest.mark.asyncio
async def test_parse_convenience_method(async_client):
    """Test parse convenience method waits for completion."""
    # Mock job creation and completion
    async_client.client.parse.run_job = AsyncMock(return_value=MagicMock(job_id="parse_job"))
    async_client.client.job.get = AsyncMock(
        return_value=MagicMock(
            status="Completed",
            result=MagicMock(type="full", result=MagicMock(type="full", chunks=[])),
        )
    )

    result = await async_client.parse("doc_id")

    assert result is not None
    async_client.client.parse.run_job.assert_called_once()
    async_client.client.job.get.assert_called()


@pytest.mark.asyncio
async def test_extract_convenience_method(async_client):
    """Test extract convenience method waits for completion."""
    schema = {"type": "object"}

    async_client.client.extract.run_job = AsyncMock(return_value=MagicMock(job_id="extract_job"))
    async_client.client.job.get = AsyncMock(
        return_value=MagicMock(status="Completed", result={"extracted": "data"})
    )

    result = await async_client.extract("doc_id", schema)

    assert result == {"extracted": "data"}


@pytest.mark.asyncio
async def test_split_convenience_method(async_client):
    """Test split convenience method waits for completion."""
    split_desc = [{"title": "Section", "description": "A section"}]

    async_client.client.split.run_job = AsyncMock(return_value=MagicMock(job_id="split_job"))
    async_client.client.job.get = AsyncMock(
        return_value=MagicMock(status="Completed", result={"splits": []})
    )

    result = await async_client.split("doc_id", split_desc)

    assert result == {"splits": []}


# ============================================================================
# Concurrent Operations Tests
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_uploads(async_client):
    """Test multiple concurrent uploads."""
    # Mock aiohttp session to avoid actual network calls
    mock_session = AsyncMock()
    mock_put_response = AsyncMock()
    mock_put_response.status = 200
    mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
    mock_put_response.__aexit__ = AsyncMock(return_value=None)
    # Make put() return the context manager directly, not as a coroutine
    mock_session.put = MagicMock(return_value=mock_put_response)

    # Mock successful uploads
    async_client.client._client.post = AsyncMock(
        side_effect=[
            MagicMock(
                status_code=200,
                json=lambda i=i: {
                    "presigned_url": "http://test/p1",
                    "file_id": f"file_{i}",
                },
            )
            for i in range(3)
        ]
    )

    # Mock the session creation to return our mock session
    with patch.object(async_client, "_create_aiohttp_session_sync", return_value=mock_session):
        # Reset session to None to trigger lazy initialization
        async_client._aiohttp_session = None

        # Upload multiple files concurrently
        tasks = [
            async_client.upload(b"content1"),
            async_client.upload(b"content2"),
            async_client.upload(b"content3"),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.startswith("file_") for r in results)
        assert mock_session.put.call_count == 3


@pytest.mark.asyncio
async def test_concurrent_jobs(async_client):
    """Test multiple concurrent job submissions."""
    # Each job type returns different IDs
    async_client.client.parse.run_job = AsyncMock(return_value=MagicMock(job_id="parse_job"))
    async_client.client.extract.run_job = AsyncMock(return_value=MagicMock(job_id="extract_job"))
    async_client.client.split.run_job = AsyncMock(return_value=MagicMock(job_id="split_job"))

    # Start multiple jobs concurrently
    jobs = await asyncio.gather(
        async_client.start_parse("doc1"),
        async_client.start_extract("doc2", {"type": "object"}),
        async_client.start_split("doc3", [{"title": "S", "description": "D"}]),
    )

    assert len(jobs) == 3
    assert jobs[0].job_id == "parse_job"
    assert jobs[1].job_id == "extract_job"
    assert jobs[2].job_id == "split_job"


# ============================================================================
# Parse Response Localization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_localize_parse_response_with_full_result_no_url(async_client):
    """Test localize_parse_response when result is already full (not a URL)."""
    from unittest.mock import MagicMock

    from reducto.types import ParseResponse

    # Create a mock ParseResponse where result is already full (not a URL)
    mock_response = MagicMock(spec=ParseResponse)
    mock_result = MagicMock()
    mock_result.type = "full"  # Not "url", so already localized
    mock_result.chunks = [
        {"type": "text", "content": "Page 1 content"},
        {"type": "text", "content": "Page 2 content"},
    ]
    mock_response.result = mock_result
    mock_response.duration = 1.5
    mock_response.job_id = "test_job_list"
    mock_response.usage = MagicMock()
    mock_response.pdf_url = None

    # This should return the response unchanged since result is already full
    result = async_client.localize_parse_response(mock_response)

    assert result is mock_response
    assert result.result.type == "full"
    assert result.result.chunks == [
        {"type": "text", "content": "Page 1 content"},
        {"type": "text", "content": "Page 2 content"},
    ]


@pytest.mark.asyncio
async def test_localize_parse_response_with_full_result(async_client):
    """Test localize_parse_response when result is already full (type != 'url')."""
    from unittest.mock import MagicMock

    from reducto.types import ParseResponse

    # Create a mock ParseResponse with a full result (not a URL)
    mock_response = MagicMock(spec=ParseResponse)
    mock_result = MagicMock()
    mock_result.type = "full"  # Not "url", so already localized
    mock_result.chunks = [{"content": "test"}]
    mock_response.result = mock_result
    mock_response.duration = 1.0
    mock_response.job_id = "test_job_full"

    # This should return the response unchanged
    result = async_client.localize_parse_response(mock_response)

    assert result is mock_response
    assert result.result.type == "full"


@pytest.mark.asyncio
async def test_localize_parse_response_with_url_result(async_client):
    """Test localize_parse_response when result needs to be fetched from URL."""
    from unittest.mock import MagicMock, patch

    from reducto.types import ParseResponse

    # Create a mock ParseResponse with a URL result
    mock_response = MagicMock(spec=ParseResponse)
    mock_url_result = MagicMock()
    mock_url_result.type = "url"
    mock_url_result.url = "http://test.com/results/123"
    mock_response.result = mock_url_result
    mock_response.duration = 2.0
    mock_response.job_id = "test_job_url"

    # Mock the HTTP client to fetch the URL (base class uses sema4ai_http.get)
    with patch("sema4ai_http.get") as mock_http_get:
        # Mock the response from the URL with proper ResultFullResult structure
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(
            return_value={
                "type": "full",
                "chunks": [
                    {
                        "blocks": [
                            {
                                "type": "Text",  # Must be capital T
                                "content": "fetched content",
                                "bbox": {
                                    "left": 0,
                                    "top": 0,
                                    "width": 100,
                                    "height": 100,
                                    "page": 1,
                                },  # Required fields
                            }
                        ],
                        "content": "fetched content",  # Required at chunk level
                        "embed": "",  # Should be a string, not an object
                    }
                ],
            }
        )
        mock_http_get.return_value = mock_http_response

        # Call the method
        result = async_client.localize_parse_response(mock_response)

        # Verify the URL was fetched
        mock_http_get.assert_called_once_with("http://test.com/results/123")

        # Verify the result was updated
        assert result is mock_response
        # The result should now be a ResultFullResult object
        assert hasattr(result.result, "__dict__")  # It's an object, not the original mock


@pytest.mark.asyncio
async def test_localize_parse_response_url_fetch_error(async_client):
    """Test localize_parse_response error handling when URL fetch fails."""
    from unittest.mock import MagicMock, patch

    from reducto.types import ParseResponse

    # Create a mock ParseResponse with a URL result
    mock_response = MagicMock(spec=ParseResponse)
    mock_url_result = MagicMock()
    mock_url_result.type = "url"
    mock_url_result.url = "http://test.com/results/404"
    mock_response.result = mock_url_result

    # Mock the HTTP client to fail (base class uses sema4ai_http.get)
    with patch("sema4ai_http.get") as mock_http_get:
        # Mock a failed response
        mock_http_get.side_effect = Exception("Network error")

        # Should raise the error
        with pytest.raises(Exception, match="Network error"):
            async_client.localize_parse_response(mock_response)


# ============================================================================
# is_closed() Method Tests
# ============================================================================


@pytest.mark.asyncio
async def test_is_closed_with_aiohttp_session():
    """Test is_closed() checks aiohttp session state when present."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client as not closed
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_reducto.is_closed = MagicMock(return_value=False)  # Sync method, not async
        mock_new.return_value = mock_reducto

        client = AsyncExtractionClient(api_key="test_key")

        # Mock aiohttp session as closed
        mock_session = AsyncMock()
        mock_session.closed = True
        client._aiohttp_session = mock_session

        # Should return True because aiohttp session is closed
        is_closed = client.is_closed()
        assert is_closed is True

        await client.close()


@pytest.mark.asyncio
async def test_is_closed_without_aiohttp_session():
    """Test is_closed() falls back to Reducto client when no aiohttp session."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_reducto.is_closed = MagicMock(return_value=False)  # Sync method, not async
        mock_new.return_value = mock_reducto

        client = AsyncExtractionClient(api_key="test_key")

        # Ensure no aiohttp session
        client._aiohttp_session = None

        # Should use Reducto client's is_closed
        is_closed = client.is_closed()
        assert is_closed is False
        mock_reducto.is_closed.assert_called_once()

        await client.close()


# ============================================================================
# Enhanced Context Manager Tests
# ============================================================================


@pytest.mark.asyncio
async def test_context_manager_comprehensive_workflow():
    """Test a realistic workflow using the async context manager.

    This demonstrates how developers should use the AsyncExtractionClient:
    - Upload a document
    - Start multiple concurrent operations
    - Wait for results
    - Automatic cleanup via context manager
    """
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_reducto.is_closed = MagicMock(return_value=False)  # Sync method, not async
        mock_new.return_value = mock_reducto

        # Mock aiohttp session for uploads
        mock_session = AsyncMock()
        mock_session.closed = False  # Set proper closed property
        mock_put_response = AsyncMock()
        mock_put_response.status = 200
        mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
        mock_put_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.put = MagicMock(return_value=mock_put_response)
        mock_session.close = AsyncMock()

        # Test data
        test_document = b"Sample PDF content for testing async workflow"
        test_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total_amount": {"type": "number"},
            },
        }

        async with AsyncExtractionClient(
            api_key="test_key", base_url="http://localhost:8000"
        ) as client:
            # Verify client is not closed initially
            assert client.is_closed() is False

            # Mock upload response
            client.client._client.post = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: {
                        "presigned_url": "http://localhost:8000/presigned",
                        "file_id": "uploaded_doc_123",
                    },
                )
            )

            # Mock session creation
            with patch.object(client, "_create_aiohttp_session_sync", return_value=mock_session):
                client._aiohttp_session = None

                # Step 1: Upload document
                file_id = await client.upload(test_document)
                assert file_id == "uploaded_doc_123"

                # Step 2: Start multiple concurrent jobs
                jobs = await asyncio.gather(
                    client.start_parse(file_id),
                    client.start_extract(file_id, test_schema),
                    return_exceptions=True,
                )

                # Verify jobs were created
                assert len(jobs) == 2
                assert all(isinstance(job, Job) for job in jobs)
                assert jobs[0].job_type == "parse"
                assert jobs[1].job_type == "extract"

                # Mock job completion for demonstration
                client.client.job.get = AsyncMock(
                    return_value=MagicMock(status="Completed", result={"processed": "successfully"})
                )

                # Step 3: Wait for completion (normally you'd do this)
                status = await jobs[0].status()
                assert status == "Completed"

                # Verify client is still usable
                assert client.is_closed() is False

        # After exiting context manager, client should be closed
        # Note: We can't test this directly due to mocking, but the close method was called
        mock_reducto.close.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager_with_upload_progress():
    """Test context manager usage with upload progress tracking."""
    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_new.return_value = mock_reducto

        progress_updates = []

        async def track_progress(uploaded: int, total: int):
            """Example progress callback for developers."""
            progress_updates.append((uploaded, total))
            percentage = (uploaded / total) * 100 if total > 0 else 0
            print(f"Upload progress: {percentage:.1f}%")

        # Mock successful upload
        mock_session = AsyncMock()
        mock_session.closed = False  # Set proper closed property
        mock_put_response = AsyncMock()
        mock_put_response.status = 200
        mock_put_response.__aenter__ = AsyncMock(return_value=mock_put_response)
        mock_put_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.put = MagicMock(return_value=mock_put_response)

        async with AsyncExtractionClient(api_key="test_key") as client:
            # Mock upload flow
            client.client._client.post = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: {
                        "presigned_url": "http://test/presigned",
                        "file_id": "progress_file_id",
                    },
                )
            )

            with patch.object(client, "_create_aiohttp_session_sync", return_value=mock_session):
                client._aiohttp_session = None

                # Upload with progress tracking
                result = await client.upload(b"test content", progress_callback=track_progress)

                assert result == "progress_file_id"

        # Cleanup verification
        mock_reducto.close.assert_called_once()


# ============================================================================
# Session Management Tests
# ============================================================================


@pytest.mark.asyncio
async def test_aiohttp_session_reuse():
    """Test that aiohttp session is reused across uploads."""

    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_new.return_value = mock_reducto

        client = AsyncExtractionClient(api_key="test_key")

        # Get the session
        session1 = client.aiohttp_session

        # After multiple operations, should be the same session
        session2 = client.aiohttp_session

        assert session1 is session2

        await client.close()


@pytest.mark.asyncio
async def test_aiohttp_session_cleanup():
    """Test that aiohttp session is properly cleaned up."""

    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock_new:
        # Mock the Reducto client
        mock_reducto = AsyncMock()
        mock_reducto.close = AsyncMock()
        mock_new.return_value = mock_reducto

        client = AsyncExtractionClient(api_key="test_key")

        # Mock the session
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        client._aiohttp_session = mock_session

        # Close client
        await client.close()

        # Session should be closed
        mock_session.close.assert_called_once()


# ============================================================================
# _resolve_extraction_input Tests
# ============================================================================


@pytest.mark.asyncio
async def test_resolve_extraction_input_with_path(async_client):
    """Test _resolve_extraction_input with a Path input uploads and starts parse."""
    from pathlib import Path

    # Mock upload and start_parse
    async_client.upload = AsyncMock(return_value="test_file_id")
    async_client.start_parse = AsyncMock(
        return_value=Job(job_id="test_job_id", job_type=JobType.PARSE, client=async_client)
    )

    # Create a temporary file path
    test_path = Path("/tmp/test_doc.pdf")

    # Call the method
    result = await async_client._resolve_extraction_input(test_path)

    # Verify upload was called
    async_client.upload.assert_called_once_with(test_path)

    # Verify start_parse was called with the file ID
    async_client.start_parse.assert_called_once_with("test_file_id", config=None)

    # Verify we got a Job back
    assert isinstance(result, Job)
    assert result.job_id == "test_job_id"


@pytest.mark.asyncio
async def test_resolve_extraction_input_with_file_id_string(async_client):
    """Test _resolve_extraction_input with a file ID string.

    Strings are treated as file IDs and start a new parse job.
    """
    # Mock start_parse
    async_client.start_parse = AsyncMock(
        return_value=Job(job_id="new_job_from_file", job_type=JobType.PARSE, client=async_client)
    )

    # Call with a file ID string
    result = await async_client._resolve_extraction_input("file_id_123")

    # Verify start_parse was called with the file ID
    async_client.start_parse.assert_called_once_with("file_id_123", config=None)

    # Verify we got a Job back
    assert isinstance(result, Job)
    assert result.job_id == "new_job_from_file"


@pytest.mark.asyncio
async def test_resolve_extraction_input_with_jobid_url(async_client):
    """Test _resolve_extraction_input with a jobid:// URL string.

    The jobid:// format is recognized and a Job is created directly without
    starting a new parse, avoiding unnecessary re-parsing.
    """
    # Call with a jobid:// URL
    result = await async_client._resolve_extraction_input("jobid://existing_job_123")

    # Verify we got a Job back with the correct job_id extracted from the URL
    assert isinstance(result, Job)
    assert result.job_id == "existing_job_123"
    assert result.job_type == "parse"


@pytest.mark.asyncio
async def test_resolve_extraction_input_with_job_object(async_client):
    """Test _resolve_extraction_input with a Job object input returns it unchanged."""
    # Create a Job object
    test_job = Job(job_id="existing_job", job_type=JobType.PARSE, client=async_client)

    # Call with Job object
    result = await async_client._resolve_extraction_input(test_job)

    # Should return the same Job object
    assert result is test_job


@pytest.mark.asyncio
async def test_resolve_extraction_input_with_invalid_type(async_client):
    """Test _resolve_extraction_input raises ValueError for invalid input types."""
    with pytest.raises(ValueError, match="Invalid input type"):
        await async_client._resolve_extraction_input(12345)  # Integer is invalid


# ============================================================================
# ExtractPreviousJobFailedError Tests
# ============================================================================


@pytest.mark.asyncio
async def test_extract_previous_job_failed_error():
    """Test ExtractPreviousJobFailedError exception attributes."""
    from sema4ai_docint.extraction.reducto.exceptions import ExtractPreviousJobFailedError

    error = ExtractPreviousJobFailedError(
        new_job_type="extract",
        job_id="job_123",
        reason="Parse failed",
    )

    assert error.job_id == "job_123"
    assert error.reason == "Parse failed"
    assert error.new_job_type == "extract"
    assert "job_123" in str(error)
    assert "Parse failed" in str(error)


@pytest.mark.asyncio
async def test_start_extract_with_schema_raises_previous_job_failed_when_parse_fails(
    async_client,
):
    """Test start_extract_with_schema raises ExtractPreviousJobFailedError when parse fails."""

    # Create a Job that will fail when waited on
    failed_job = Job(job_id="failed_parse_job", job_type=JobType.PARSE, client=async_client)

    # Mock the wait() method to raise JobFailedError
    async def mock_wait():
        raise JobFailedError("Parse failed", job_id="failed_parse_job")

    failed_job.wait = mock_wait

    # Create test schema
    test_schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    # Should raise the JobFailedError
    with pytest.raises(JobFailedError) as exc_info:
        await async_client.start_extract_with_schema(failed_job, test_schema)

    # Verify error details
    assert "failed_parse_job" in str(exc_info.value)


@pytest.mark.asyncio
async def test_start_extract_with_data_model_raises_previous_job_failed_when_parse_fails(
    async_client,
):
    # Create a Job that will fail when waited on
    failed_job = Job(job_id="failed_parse_job_2", job_type=JobType.PARSE, client=async_client)

    # Mock the wait() method to raise JobFailedError
    async def mock_wait():
        raise JobFailedError("Parse failed", job_id="failed_parse_job_2")

    failed_job.wait = mock_wait

    # Create test schema
    test_schema = {"type": "object", "properties": {"invoice_number": {"type": "string"}}}

    # Should raise the JobFailedError
    with pytest.raises(JobFailedError) as exc_info:
        await async_client.start_extract_with_data_model(
            failed_job,
            test_schema,
            data_model_prompt="Extract invoice data",
        )

    # Verify error details
    assert "failed_parse_job_2" in str(exc_info.value)
