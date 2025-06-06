import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
import requests
from agent_platform.orchestrator.agent_server_client import (
    AgentServerClient,
    print_header,
    print_success,
)
from fastapi import status

# Path to the cloud server script
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
    """Start the cloud server for testing if not already running."""
    if is_port_in_use(8001):
        print("Cloud server already running on port 8001")
        yield "http://localhost:8001"
        return

    print("Starting cloud server on port 8001")
    server_process = subprocess.Popen(
        [sys.executable, str(CLOUD_SERVER_PATH)],
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    # Wait for the server to start
    time.sleep(2)  # Give the server time to start

    # Check if server is running
    try:
        requests.get("http://localhost:8001")
    except requests.ConnectionError as e:
        server_process.terminate()
        server_process.wait()
        raise Exception("Cloud server failed to start") from e

    yield "http://localhost:8001"

    # Cleanup: terminate the server only if we started it
    server_process.send_signal(signal.SIGTERM)
    server_process.wait()

    # Clean up the temp_uploads directory
    temp_uploads_dir = Path(CLOUD_SERVER_PATH).parent / "temp_uploads"
    if temp_uploads_dir.exists():
        import shutil

        shutil.rmtree(temp_uploads_dir)
        print("Cleaned up temp_uploads directory")


def _file_uploads_with_existing_thread(
    agent_client: AgentServerClient,
    thread_id: str,
    agent_id: str,
    create_sample_file: Callable,
) -> None:
    """Test file upload functionality for threads."""
    print_header("TESTING FILE UPLOADS")

    # Upload single file to thread
    thread_file, thread_key, thread_value = create_sample_file()
    thread_response = agent_client.upload_file_to_thread(
        thread_id,
        thread_file,
        embedded=True,
    )
    assert thread_response.status_code == status.HTTP_200_OK, (
        f"File upload to thread: bad response: {thread_response.status_code} {thread_response.text}"
    )
    print_success("Successfully uploaded file to thread")

    # Upload multiple files to thread
    multi_files = [create_sample_file()[0] for _ in range(4)]
    thread_files = multi_files[:2]
    thread_multi_response = agent_client.upload_files_to_thread(
        thread_id,
        thread_files,
    )
    assert thread_multi_response.status_code == status.HTTP_200_OK, (
        f"Multiple file upload to thread: "
        f"bad response: {thread_multi_response.status_code} "
        f"{thread_multi_response.text}"
    )
    print_success("Successfully uploaded multiple files to thread")

    # Get files from thread
    total_files = 1 + 2
    thread_file_refs = agent_client.list_files(thread_id)
    assert thread_file_refs is not None, "Thread file refs not found"
    assert len(thread_file_refs) == total_files, (
        f"Expected {total_files} files, got {len(thread_file_refs)}"
    )
    print_success(f"Successfully listed {len(thread_file_refs)} files")

    # Get file by ref
    file_id = next(iter(thread_file_refs.keys()))
    file_ref = thread_file_refs[file_id]
    file_info = agent_client.get_file_info_by_ref(thread_id, file_ref)
    assert file_info is not None, "File info not found"
    assert file_info["file_id"] == file_id, (
        f"Expected file ID {file_id}, got {file_info['file_id']}"
    )
    assert file_info["file_path"] is not None, "File path not found"
    assert file_info["file_url"] is not None, "File URL not found"
    assert file_info["file_path"] == file_info["file_url"], "File path and URL should be the same"
    print_success(f"Successfully got file info for {file_id}")

    # Verify that the file_path is a presigned URL from the cloud server
    assert "file_url" in file_info, "File URL not found in file info"
    assert file_info["file_url"] is not None, "File URL is None"
    assert file_info["file_url"] == file_info["file_path"], (
        f"Expected file URL to be the same as file path: "
        f"{file_info['file_url']} != {file_info['file_path']}"
    )
    file_path = file_info.get("file_path")
    assert file_path is not None, "File path not found in file info"
    assert file_path.startswith("http://localhost:8001/download/"), (
        f"Expected file path to be a presigned URL starting with "
        f"'http://localhost:8001/download/', got '{file_path}'"
    )
    assert "token=" in file_path, "File path should contain a token parameter for presigned URL"
    assert file_id in file_path, f"File path should contain the file_id '{file_id}'"
    print_success("Successfully verified that file_path is a presigned URL from cloud server")

    # Download file by ref
    file_content = agent_client.download_file_by_ref(thread_id, file_ref)
    assert file_content is not None, "File content not found"
    assert len(file_content) > 0, "File content is empty"
    print_success(f"Successfully downloaded file {file_id} with size {len(file_content)} bytes")

    # Delete file from thread
    agent_client.delete_file_by_ref(thread_id, file_id)
    thread_files = agent_client.list_files(thread_id)
    assert thread_files is not None, "Thread files not found"
    assert len(thread_files) == total_files - 1, (
        f"Expected {total_files - 1} files, got {len(thread_files)}"
    )
    print_success(f"Successfully deleted file {file_id} from thread")

    # Delete all files from thread
    agent_client.delete_all_files_from_thread(thread_id)
    empty_thread_files = agent_client.list_files(thread_id)
    assert empty_thread_files is not None, "Thread files not found"
    assert len(empty_thread_files) == 0, f"Expected 0 files, got {len(empty_thread_files)}"
    print_success("Successfully deleted all files from thread")

    print_success("Successfully tested file uploads with existing thread")


def _file_uploads_with_non_existent_thread(
    agent_client: AgentServerClient,
    agent_id: str,
    create_sample_file: Callable,
) -> None:
    """Test file upload functionality with a non-existent thread ID."""
    print_header("TESTING FILE UPLOADS WITH NON-EXISTENT THREAD ID")

    non_existent_thread_id = str(uuid.uuid4())
    thread_file, thread_key, thread_value = create_sample_file()

    # Upload single file to non-existent thread
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error uploading file to thread: 404 "
            r"{\"detail\":\"Thread [0-9a-f-]+ not found\"}"
        ),
    ):
        _ = agent_client.upload_file_to_thread(
            non_existent_thread_id,
            thread_file,
            embedded=True,
        )
    print_success("Successfully tested file upload with non-existent thread")

    # Upload multiple files to non-existent thread
    multi_files = [create_sample_file()[0] for _ in range(4)]
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error uploading file to thread: 404 "
            r"{\"detail\":\"Thread [0-9a-f-]+ not found\"}"
        ),
    ):
        _ = agent_client.upload_files_to_thread(non_existent_thread_id, multi_files)
    print_success("Successfully tested multiple file upload with non-existent thread")

    # Test getting files from non-existent thread
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error getting files from thread: 404 "
            r"{\"detail\":\"Thread [0-9a-f-]+ not found\"}"
        ),
    ):
        _ = agent_client.list_files(non_existent_thread_id)
    print_success("Successfully tested getting files from non-existent thread")

    # Test getting file by ref from non-existent thread
    non_existent_file_ref = "non-existent-file-ref"
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error getting file by ref: 404 "
            r"{\"detail\":\"Thread [0-9a-f-]+ not found\"}"
        ),
    ):
        _ = agent_client.get_file_info_by_ref(
            non_existent_thread_id,
            non_existent_file_ref,
        )
    print_success("Successfully tested getting file by ref from non-existent thread")

    # Test downloading file by ref from non-existent thread
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error downloading file: 404 {\"detail\":\"Thread [0-9a-f-]+ "
            r"not found\"}"
        ),
    ):
        _ = agent_client.download_file_by_ref(
            non_existent_thread_id,
            non_existent_file_ref,
        )
    print_success("Successfully tested downloading file from non-existent thread")

    # Test deleting all files from non-existent thread
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error deleting all files from thread: 404 "
            r"{\"detail\":\"Thread [0-9a-f-]+ not found\"}"
        ),
    ):
        _ = agent_client.delete_all_files_from_thread(non_existent_thread_id)
    print_success("Successfully tested deleting all files from non-existent thread")

    print_success("Successfully tested file uploads with non-existent thread")


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_file_uploads(
    base_url_agent_server_sqlite_cloud,
    base_url_agent_server_postgres_cloud,
    create_sample_file,
    cloud_server,
):
    """Test file upload functionality using the agent server client."""
    print_header("TESTING SQLITE FILE UPLOADS")
    with AgentServerClient(base_url_agent_server_sqlite_cloud) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id()
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Test with a valid thread ID (SQLite)
        _file_uploads_with_existing_thread(
            agent_client,
            thread_id,
            agent_id,
            create_sample_file,
        )

        # Test with a non-existent thread ID (SQLite)
        _file_uploads_with_non_existent_thread(
            agent_client,
            agent_id,
            create_sample_file,
        )

    print_header("TESTING POSTGRES FILE UPLOADS")
    with AgentServerClient(base_url_agent_server_postgres_cloud) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id()
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Test with a valid thread ID (Postgres)
        _file_uploads_with_existing_thread(
            agent_client,
            thread_id,
            agent_id,
            create_sample_file,
        )

        # Test with a non-existent thread ID (Postgres)
        _file_uploads_with_non_existent_thread(
            agent_client,
            agent_id,
            create_sample_file,
        )


if __name__ == "__main__":
    import os
    import sys

    import pytest

    os.environ["INTEGRATION_TEST_START_SERVER"] = "true"
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
