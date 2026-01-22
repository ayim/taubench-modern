"""
Pytest plugin providing a mock cloud file management server for testing.

This plugin provides the `cloud_server` fixture which starts a FastAPI-based
mock server on port 8001 that simulates cloud file storage operations
(presigned URLs, uploads, downloads, deletions).

Usage:
    Register this plugin in your conftest.py or pytest_plugins:

        pytest_plugins = ["server.tests.files.cloud_server_fixtures"]

    Then use the fixture in your tests:

        def test_file_upload(cloud_server):
            # cloud_server is "http://localhost:8001"
            ...
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

CLOUD_SERVER_PATH = Path(__file__).parent / "cloud_server.py"


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except OSError:
            return True


@pytest.fixture(scope="session")
def cloud_server():
    """Start the cloud server for testing if not already running.

    This fixture starts a mock file management server on port 8001 that provides:
    - POST / : Get presigned POST URL for file upload
    - GET / : Get presigned download URL
    - DELETE / : Delete a file
    - POST /upload : Handle actual file upload
    - GET /download/{fileId} : Download a file

    The server is started once per test session and cleaned up automatically.

    Yields:
        str: The base URL of the cloud server ("http://localhost:8001")
    """
    server_process = None

    if is_port_in_use(8001):
        print("Cloud server already running on port 8001")
    else:
        print("Starting cloud server on port 8001")
        server_process = subprocess.Popen(
            [sys.executable, str(CLOUD_SERVER_PATH)],
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        time.sleep(2)  # Give the server time to start

        try:
            requests.get("http://localhost:8001")
        except requests.ConnectionError as e:
            server_process.terminate()
            server_process.wait()
            raise Exception("Cloud server failed to start") from e

    try:
        yield "http://localhost:8001"
    finally:
        temp_uploads_dir = Path(CLOUD_SERVER_PATH).parent / "temp_uploads"
        if temp_uploads_dir.exists():
            import shutil

            shutil.rmtree(temp_uploads_dir)
            print("Cleaned up temp_uploads directory")

        if server_process:
            server_process.send_signal(signal.SIGTERM)
            server_process.wait()
            print("Terminated cloud server")
