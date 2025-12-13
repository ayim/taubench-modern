import uuid
from collections.abc import Callable

import pytest
import requests
from agent_platform.orchestrator.agent_server_client import (
    AgentServerClient,
    print_header,
    print_success,
)
from fastapi import status


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
    assert len(thread_file_refs) == total_files, f"Expected {total_files} files, got {len(thread_file_refs)}"
    print_success(f"Successfully listed {len(thread_file_refs)} files")

    # Get file by ref
    file_id = next(iter(thread_file_refs.keys()))
    file_ref = thread_file_refs[file_id]
    file_info = agent_client.get_file_info_by_ref(thread_id, file_ref)
    assert file_info is not None, "File info not found"
    assert file_info["file_id"] == file_id, f"Expected file ID {file_id}, got {file_info['file_id']}"
    # Checking if file_url is present in file_info
    assert "file_url" in file_info.keys(), "Expected file URL to be present in file data"
    assert file_info["file_url"] == file_info["file_path"], "Expected file URL to be the same as file path"

    print_success(f"Successfully got file info for {file_id}")

    # Download file by ref
    file_content = agent_client.download_file_by_ref(thread_id, file_ref)
    assert file_content is not None, "File content not found"
    assert len(file_content) > 0, "File content is empty"
    print_success(f"Successfully downloaded file {file_id} with size {len(file_content)} bytes")

    # Delete file from thread
    agent_client.delete_file_by_ref(thread_id, file_id)
    thread_files = agent_client.list_files(thread_id)
    assert thread_files is not None, "Thread files not found"
    assert len(thread_files) == total_files - 1, f"Expected {total_files - 1} files, got {len(thread_files)}"
    print_success(f"Successfully deleted file {file_id} from thread")

    # Delete all files from thread
    agent_client.delete_all_files_from_thread(thread_id)
    empty_thread_files = agent_client.list_files(thread_id)
    assert empty_thread_files is not None, "Thread files not found"
    assert len(empty_thread_files) == 0, f"Expected 0 files, got {len(empty_thread_files)}"
    print_success("Successfully deleted all files from thread")

    # Test Unicode filenames through FastAPI serialization
    print_header("TESTING UNICODE FILENAME SERIALIZATION")
    unicode_filenames = [
        "テスト_ファイル.txt",  # Japanese
        "测试文件.csv",  # Chinese
        "тестовый_файл.json",  # Russian
        "αρχείο_δοκιμής.xml",  # Greek
    ]

    unicode_file_ids = {}
    for filename in unicode_filenames:
        file_content = f"Test content for {filename}".encode()
        response = agent_client.upload_file_to_thread(
            thread_id,
            filename,
            content=file_content,
            embedded=True,
        )
        assert response.status_code == status.HTTP_200_OK, f"Failed to upload Unicode filename {filename}"
        response_data = response.json()
        assert response_data[0]["file_ref"] == filename
        unicode_file_ids[filename] = response_data[0]["file_id"]

    # Verify listing preserves Unicode filenames
    unicode_files = agent_client.list_files(thread_id)
    assert unicode_files is not None
    assert len(unicode_files) == len(unicode_filenames)
    for filename, file_id in unicode_file_ids.items():
        assert unicode_files[file_id] == filename

    # Verify get file info preserves Unicode filenames
    for filename, file_id in unicode_file_ids.items():
        file_info = agent_client.get_file_info_by_ref(thread_id, filename)
        assert file_info is not None, f"File info not found for {filename}"
        assert file_info["file_ref"] == filename
        assert file_info["file_id"] == file_id

    # Verify download by Unicode filename works
    for filename in unicode_filenames:
        content = agent_client.download_file_by_ref(thread_id, filename)
        expected = f"Test content for {filename}".encode()
        assert content == expected, f"Content mismatch for {filename}"

    # Clean up Unicode files
    agent_client.delete_all_files_from_thread(thread_id)
    empty_files = agent_client.list_files(thread_id)
    assert empty_files is not None, "Failed to get thread files after deletion"
    assert len(empty_files) == 0, "Failed to delete all files"

    print_success("Successfully tested Unicode filename serialization")
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
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
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
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
        ),
    ):
        _ = agent_client.upload_files_to_thread(non_existent_thread_id, multi_files)
    print_success("Successfully tested multiple file upload with non-existent thread")
    # Test getting files from non-existent thread
    with pytest.raises(
        requests.exceptions.HTTPError,
        match=(
            r"Error getting files from thread: 404 "
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
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
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
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
            r"Error downloading file: 404 "
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
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
            r"\{\"error\":\{.*\"message\":\"Thread [0-9a-f-]+ not found\".*\}\}"
        ),
    ):
        _ = agent_client.delete_all_files_from_thread(non_existent_thread_id)
    print_success("Successfully tested deleting all files from non-existent thread")

    print_success("Successfully tested file uploads with non-existent thread")


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
def test_file_uploads(
    base_url_agent_server_sqlite,
    base_url_agent_server_postgres,
    create_sample_file,
):
    """Test file upload functionality using the agent server client."""
    print_header("TESTING SQLITE FILE UPLOADS")
    with AgentServerClient(base_url_agent_server_sqlite) as agent_client:
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
    with AgentServerClient(base_url_agent_server_postgres) as agent_client:
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
