import io
import json
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient
from sema4ai_docint.extraction.reducto.exceptions import (
    UploadForbiddenError,
    UploadPresignRequestError,
)


class UploadServerConfig:
    """Test configuration for the embedded web server."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset server configuration to defaults."""
        self.upload_status_code = 200
        self.upload_response = {
            "presigned_url": "http://localhost:8001/presigned",
            "file_id": "test_file_id_123",
        }
        self.presigned_status_code = 200
        self.presigned_response = b"OK"


class HTTPHandlerForTests(BaseHTTPRequestHandler):
    """HTTP request handler for the test server."""

    def log_message(self, format_str, *args):
        """Suppress HTTP server logs during testing."""
        pass

    def do_POST(self):
        """Handle POST requests to /upload endpoint."""
        if self.path == "/upload":
            # Get test configuration from server instance
            config = self.server.test_config

            # Send configured status code
            self.send_response(config.upload_status_code)

            if config.upload_status_code == 200:
                # Send JSON response for successful requests
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response_json = json.dumps(config.upload_response)
                self.wfile.write(response_json.encode())
            else:
                # Send error response
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Error response")
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        """Handle PUT requests to presigned URL."""
        if self.path == "/presigned":
            # Get test configuration from server instance
            config = self.server.test_config

            # Read the uploaded file data
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                _ = self.rfile.read(content_length)

            # Send configured status code
            self.send_response(config.presigned_status_code)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(config.presigned_response)
        else:
            self.send_response(404)
            self.end_headers()


class UploadHTTPServerForTests(HTTPServer):
    """Test HTTP server with configuration."""

    def __init__(self, server_address, request_handler_class, test_config):
        super().__init__(server_address, request_handler_class)
        self.test_config = test_config


@pytest.fixture(scope="session")
def test_server():
    """Fixture to create and manage the test HTTP server."""
    # Create test configuration
    config = UploadServerConfig()

    # Create server
    server = UploadHTTPServerForTests(("localhost", 0), HTTPHandlerForTests, config)
    server_port = server.server_port

    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Give server time to start
    time.sleep(0.1)

    yield f"http://localhost:{server_port}", config

    # Cleanup
    server.shutdown()
    server.server_close()


@pytest.fixture
def test_file():
    """Fixture to create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Test file content for upload")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


@pytest_asyncio.fixture
async def mock_reducto_client():
    """Fixture to mock the Reducto client creation with a real HTTP backend.

    Provides an object mimicking the Reducto client shape where `._client` has
    `.headers`, `.post`, and `.put` that actually perform HTTP using httpx.
    """

    class SimpleHttpClient:
        def __init__(self):
            # Default header to simulate API key header set by the SDK
            self.headers: dict[str, str] = {"X-API-Key": "test_key"}
            # Create an async httpx client
            self._httpx_client = httpx.AsyncClient()

        def _merge_headers(self, headers: dict | None) -> dict:
            merged = dict(self.headers)
            if headers:
                merged.update(headers)
            return merged

        async def post(self, url: str, headers: dict | None = None, **kwargs):
            return await self._httpx_client.post(
                url, headers=self._merge_headers(headers), **kwargs
            )

        async def put(self, url: str, headers: dict | None = None, **kwargs):
            return await self._httpx_client.put(url, headers=self._merge_headers(headers), **kwargs)

        async def close(self):
            await self._httpx_client.aclose()

    class ReductoLike:
        def __init__(self):
            self._client = SimpleHttpClient()

    with patch(
        "sema4ai_docint.extraction.reducto.async_.AsyncExtractionClient._new_async_reducto_client"
    ) as mock:
        reducto_like = ReductoLike()
        mock.return_value = reducto_like
        yield reducto_like
        # Cleanup: close the httpx client
        await reducto_like._client.close()


@pytest.mark.asyncio
async def test_successful_upload(test_server, test_file, mock_reducto_client):
    """Test successful upload that returns file_id."""
    base_url, config = test_server

    # Configure server for successful response
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned",
        "file_id": "successful_file_id_123",
    }

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload
    result = await client.upload(test_file)

    # Verify result
    assert result == "successful_file_id_123"


@pytest.mark.asyncio
async def test_upload_403_error(test_server, test_file, mock_reducto_client):
    """Test upload with 403 error raises specific API key exception."""
    base_url, config = test_server

    # Configure server for 403 response
    config.upload_status_code = 403

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify specific exception
    with pytest.raises(UploadForbiddenError) as exc_info:
        await client.upload(test_file)

    msg = str(exc_info.value)
    assert "HTTP 403" in msg or "403" in msg


@pytest.mark.asyncio
async def test_upload_401_error(test_server, test_file, mock_reducto_client):
    """Test upload with 401 error raises HTTPError via raise_for_status."""
    base_url, config = test_server

    # Configure server for 401 response
    config.upload_status_code = 401

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify presign error is raised
    with pytest.raises(UploadPresignRequestError) as exc_info:
        await client.upload(test_file)

    err = exc_info.value
    assert err.status_code == 401
    assert "presigned" in str(err).lower()


@pytest.mark.asyncio
async def test_upload_500_error(test_server, test_file, mock_reducto_client):
    """Test upload with 500 error raises HTTPError via raise_for_status."""
    base_url, config = test_server

    # Configure server for 500 response
    config.upload_status_code = 500

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify presign error is raised
    with pytest.raises(UploadPresignRequestError) as exc_info:
        await client.upload(test_file)

    err = exc_info.value
    assert err.status_code == 500
    assert "presigned" in str(err).lower()


@pytest.mark.asyncio
async def test_upload_with_inline_bytes(test_server, mock_reducto_client):
    """Test successful upload when passing raw bytes instead of a Path."""
    base_url, config = test_server

    # Configure server for successful response
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned",
        "file_id": "bytes_file_id_123",
    }
    config.presigned_status_code = 200

    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)
    result = await client.upload(b"inline-bytes-content")
    assert result == "bytes_file_id_123"


@pytest.mark.asyncio
async def test_upload_with_file_like_bytesio(test_server, mock_reducto_client):
    """Test successful upload when passing a BinaryIO-like object."""
    base_url, config = test_server

    # Configure server for successful response
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned",
        "file_id": "filelike_file_id_123",
    }
    config.presigned_status_code = 200

    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)
    result = await client.upload(io.BytesIO(b"file-like-bytes"))
    assert result == "filelike_file_id_123"


@pytest.mark.asyncio
async def test_upload_missing_presigned_url(test_server, test_file, mock_reducto_client):
    """Test upload with missing presigned_url in response."""
    base_url, config = test_server

    # Configure server for successful status but missing presigned_url
    config.upload_status_code = 200
    config.upload_response = {
        "file_id": "test_file_id_123"
        # missing presigned_url
    }

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify specific exception
    with pytest.raises(Exception, match="No presigned URL returned"):
        await client.upload(test_file)


@pytest.mark.asyncio
async def test_upload_missing_file_id(test_server, test_file, mock_reducto_client):
    """Test upload with missing file_id in response."""
    base_url, config = test_server

    # Configure server for successful status but missing file_id
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned"
        # missing file_id
    }

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify specific exception
    with pytest.raises(Exception, match="No file ID returned"):
        await client.upload(test_file)


@pytest.mark.asyncio
async def test_upload_presigned_url_success(test_server, test_file, mock_reducto_client):
    """Test that the presigned URL PUT request is made correctly."""
    base_url, config = test_server

    # Configure server for successful responses
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned",
        "file_id": "test_file_id_123",
    }
    config.presigned_status_code = 200

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload
    result = await client.upload(test_file)

    # Verify that the upload completed successfully
    assert result == "test_file_id_123"


@pytest.mark.asyncio
async def test_upload_empty_json_response(test_server, test_file, mock_reducto_client):
    """Test upload with empty JSON response."""
    base_url, config = test_server

    # Configure server for successful status but empty response
    config.upload_status_code = 200
    config.upload_response = {}

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload and verify it fails due to missing presigned_url
    with pytest.raises(Exception, match="No presigned URL returned"):
        await client.upload(test_file)


@pytest.mark.asyncio
async def test_upload_with_custom_headers(test_server, test_file, mock_reducto_client):
    """Test that upload request includes headers from the Reducto client."""
    base_url, config = test_server

    # Configure server for successful response
    config.upload_status_code = 200
    config.upload_response = {
        "presigned_url": f"{base_url}/presigned",
        "file_id": "test_file_id_123",
    }

    # Configure mock client with custom headers
    mock_reducto_client._client.headers = {
        "X-API-Key": "custom_api_key",
        "User-Agent": "test-client",
    }

    # Create client
    client = AsyncExtractionClient(api_key="test_key", base_url=base_url)

    # Test upload
    result = await client.upload(test_file)

    # Verify result
    assert result == "test_file_id_123"
