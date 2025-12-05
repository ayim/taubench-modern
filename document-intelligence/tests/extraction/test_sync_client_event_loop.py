"""Test that demonstrates the event loop bug in SyncExtractionClient.

This test demonstrates that SyncExtractionClient fails on the second call when
using asyncio.run() because the cached aiohttp session is tied to a closed event loop.

The issue is that:
1. SyncExtractionClient wraps AsyncExtractionClient and uses asyncio.run() for each call
2. AsyncExtractionClient caches an aiohttp.ClientSession
3. Each asyncio.run() call creates a new event loop and closes it when done
4. The cached session remains tied to the first (now closed) event loop
5. Subsequent calls fail with "RuntimeError: Event loop is closed"
"""

import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from sema4ai_docint.extraction.reducto.sync import SyncExtractionClient


class SimpleUploadHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for upload testing."""

    request_count = 0

    def log_message(self, format_str, *args):
        """Suppress HTTP server logs."""
        pass

    def do_POST(self):
        """Handle POST to /upload."""
        if self.path == "/upload":
            SimpleUploadHandler.request_count += 1
            response = {
                "presigned_url": f"http://localhost:8766/presigned/{SimpleUploadHandler.request_count}",
                "file_id": f"test_file_id_{SimpleUploadHandler.request_count}",
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        """Handle PUT to presigned URL."""
        if self.path.startswith("/presigned/"):
            content_length = int(self.headers.get("Content-Length", 0))
            _ = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def simple_server():
    """Start a simple HTTP server."""
    SimpleUploadHandler.request_count = 0

    # Create server with SO_REUSEADDR to allow quick restart
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("localhost", 8766), SimpleUploadHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    yield server

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_sync_client_supports_multiple_sequential_uploads(simple_server):
    """Test that SyncExtractionClient can handle multiple sequential uploads.

    This test proves the review comment: The synchronous wrapper delegates to
    AsyncExtractionClient by calling asyncio.run(...) for each operation, but the
    async client caches an aiohttp.ClientSession tied to an event loop. Because
    asyncio.run creates and then closes a new loop on every call, the cached
    session becomes unusable after the first call.

    This test currently FAILS but should PASS once the sync client is fixed.
    """
    client = SyncExtractionClient(
        api_key="test_api_key",
        base_url="http://localhost:8766",
        disable_ssl_verification=True,
    )

    # Should be able to upload multiple documents with the same client
    file_id_1 = client.upload(b"document 1 content")
    assert file_id_1 == "test_file_id_1"

    file_id_2 = client.upload(b"document 2 content")
    assert file_id_2 == "test_file_id_2"

    file_id_3 = client.upload(b"document 3 content")
    assert file_id_3 == "test_file_id_3"


def test_sync_client_supports_bytesio_uploads(simple_server):
    """Test that SyncExtractionClient can handle BytesIO uploads multiple times.

    Currently FAILS but should PASS once the sync client is fixed.
    """
    client = SyncExtractionClient(
        api_key="test_api_key",
        base_url="http://localhost:8766",
        disable_ssl_verification=True,
    )

    # Should be able to upload multiple BytesIO objects
    file_id_1 = client.upload(io.BytesIO(b"document 1 content"))
    assert file_id_1 == "test_file_id_1"

    file_id_2 = client.upload(io.BytesIO(b"document 2 content"))
    assert file_id_2 == "test_file_id_2"


def test_sync_client_supports_file_path_uploads(simple_server, tmp_path):
    """Test that SyncExtractionClient can handle file path uploads multiple times.

    Currently FAILS but should PASS once the sync client is fixed.
    """
    client = SyncExtractionClient(
        api_key="test_api_key",
        base_url="http://localhost:8766",
        disable_ssl_verification=True,
    )

    # Create test files
    file1 = tmp_path / "doc1.txt"
    file1.write_bytes(b"document 1 content")

    file2 = tmp_path / "doc2.txt"
    file2.write_bytes(b"document 2 content")

    # Should be able to upload multiple files
    file_id_1 = client.upload(file1)
    assert file_id_1 == "test_file_id_1"

    file_id_2 = client.upload(file2)
    assert file_id_2 == "test_file_id_2"
