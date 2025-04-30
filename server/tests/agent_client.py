import itertools
import os
from datetime import UTC, datetime
from functools import partial
from typing import Literal
from urllib.parse import urljoin

import requests
from fastapi import status

from agent_platform.core.actions import ActionPackage

HEADER_INDEX = 0

DEBUG = True


def print_header(message):
    if DEBUG:
        global HEADER_INDEX  # noqa: PLW0603
        HEADER_INDEX += 1
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        header = f"[{timestamp}] {HEADER_INDEX}. {message}"
        print(f"\n\033[94m{header}\033[0m")  # Blue color
        print("-" * len(header))


def print_success(message):
    if DEBUG:
        print(f"\033[92mSUCCESS\033[0m: {message}")  # Green color


def print_error(message):
    if DEBUG:
        print(f"\033[91mERROR\033[0m: {message}")  # Red color


def print_warning(message):
    if DEBUG:
        print(f"\033[93mWARNING\033[0m: {message}")  # Yellow color


def print_info(message):
    if DEBUG:
        print(f"\033[94mINFO\033[0m: {message}")  # Blue color


class AgentServerClient:
    """
    A client for interacting with the agent server.
    """

    def __init__(self, base_url: str):
        """
        Args:
            base_url: The base URL of the agent server.
        """

        if not base_url.endswith("/api/v2"):
            base_url = urljoin(base_url + "/", "api/v2")
        self.base_url = base_url
        self._created_agent_ids: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.remove_created_agents()

    def delete_agent(self, agent_id: str):
        """Delete an agent by ID."""
        url = urljoin(self.base_url + "/", f"agents/{agent_id}")
        response = requests.delete(url)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            print_success(f"Successfully deleted agent with ID: {agent_id}")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code} "
                f"when deleting agent {agent_id}",
            )

    def remove_created_agents(self):
        """Removes all agents that were created by the client."""
        for agent_id in self._created_agent_ids:
            self.delete_agent(agent_id)

    def list_files(self, thread_id: str) -> dict[str, str] | None:
        """
        Lists all files in the specified thread.

        Returns: A dictionary of file IDs and their corresponding references.
        """
        base_url_api = f"{self.base_url}"
        url = urljoin(base_url_api + "/", f"threads/{thread_id}/files")
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)
        if response.status_code == status.HTTP_200_OK:
            response_data = response.json()
            files = dict()
            for entry in response_data:
                files[entry["file_id"]] = entry["file_ref"]
            return files
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error getting files from thread: {response.status_code} "
                    f"{response.text}",
                ) from e

    def get_file_info_by_ref(
        self,
        thread_id: str,
        file_ref: str,
    ) -> dict | None:
        """Retrieves a file using the new get-file endpoint."""
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/file-by-ref")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        params = {"file_ref": file_ref}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == status.HTTP_200_OK:
            return response.json()
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error getting file by ref: {response.status_code} "
                    f"{response.text}",
                ) from e

    def get_file_by_ref(
        self,
        thread_id: str,
        file_ref: str,
        output_type: Literal["str", "bytes"] = "str",
    ) -> str | bytes:
        from pathlib import Path
        from urllib.parse import urlparse

        from agent_platform.server.file_manager import url_to_fs_path

        file_info = self.get_file_info_by_ref(thread_id, file_ref)
        file_url = file_info.get("file_url") if file_info else None
        if not file_url:
            raise ValueError(
                f"file_url not available in response. Response: {file_info}",
            )

        parsed_url = urlparse(file_url)
        if parsed_url.scheme == "file":
            p = Path(url_to_fs_path(file_url))
            if output_type == "str":
                return p.read_text()
            elif output_type == "bytes":
                return p.read_bytes()
            raise ValueError(f"Unsupported output type: {output_type}")
        raise RuntimeError(
            f"Unsupported file scheme: {parsed_url.scheme} (must implement)",
        )

    def download_file_by_ref(self, thread_id: str, file_ref: str) -> bytes:
        """
        Downloads a file by its reference using the streaming endpoint.

        Args:
            thread_id: The ID of the thread containing the file.
            file_ref: The reference of the file to download.

        Returns:
            The file content as bytes.

        Raises:
            HTTPError: If the file could not be downloaded.
        """
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/files/download/")
        params = {"file_ref": file_ref}

        response = requests.get(url, params=params, stream=True)
        try:
            response.raise_for_status()
            # Read all content in chunks
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
            return content
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error downloading file: {response.status_code} {response.text}",
            ) from e

    _next_agent_id = partial(next, itertools.count())

    def delete_file_by_ref(self, thread_id: str, file_ref: str) -> None:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/files/{file_ref}")
        response = requests.delete(url)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            print_success(
                f"Successfully deleted file {file_ref} from thread {thread_id}",
            )
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error deleting file {file_ref} from thread {thread_id}: "
                    f"{response.status_code} {response.text}",
                ) from e

    def delete_all_files_from_thread(self, thread_id: str) -> None:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/files")
        response = requests.delete(url)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            print_success(f"Successfully deleted all files from thread {thread_id}")
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error deleting all files from thread: {response.status_code} "
                    f"{response.text}",
                ) from e

    def create_agent_and_return_agent_id(
        self,
        *,
        name: str = "",
        action_packages: list[ActionPackage] | None = None,
        runbook: str = "This is a test runbook",
        description: str = "This is a test agent",
    ) -> str:
        print_header("CREATING AGENT")

        from dataclasses import asdict

        url = urljoin(self.base_url + "/", "agents")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not name:
            name = f"Test Agent {self._next_agent_id()}"

        action_packages_raw: list[dict] = (
            [asdict(ap) for ap in action_packages] if action_packages else []
        )
        data = {
            "mode": "conversational",
            "name": name,
            "version": "1.0.0",
            "description": description,
            "runbook": runbook,
            "action_packages": action_packages_raw,
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
            "observability_configs": [],
            "question_groups": [],
            "platform_configs": [],
            "extra": {
                "test": "test",
            },
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == status.HTTP_200_OK:
            agent_id = response.json()["agent_id"]
            assert agent_id is not None, "Agent id is None right after creation"
            print_success(f"Created agent with ID: {agent_id}")

            self._created_agent_ids.append(agent_id)
            return agent_id
        else:
            raise Exception(
                f"Error creating agent: {response.status_code} {response.text}",
            )

    def create_thread_and_return_thread_id(self, agent_id: str) -> str:
        """
        Creates a new thread for the given agent.
        """
        print_header("CREATING THREAD")
        url = urljoin(self.base_url + "/", "threads")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "agent_id": agent_id,
            "name": "Test Thread",
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == status.HTTP_200_OK:
            thread_id = response.json()["thread_id"]
        else:
            raise Exception(
                f"Error creating thread: {response.status_code} {response.text}",
            )

        assert thread_id is not None, "Thread id is None right after creation"
        print_success(f"Created thread with ID: {thread_id}")
        return thread_id

    def upload_file_to_thread(
        self,
        thread_id: str,
        file_path: str,
        *,
        content: bytes | None = None,
        embedded: bool | None = None,
    ):
        import io

        kwargs = {}
        if embedded is not None:
            kwargs["data"] = {"embedded": embedded}

        url = urljoin(self.base_url + "/", f"threads/{thread_id}/files")
        if content is None:
            with open(file_path, "rb") as file:
                files = {"files": (os.path.basename(file_path), file, "text/plain")}
                response = requests.post(url, files=files, **kwargs)
        else:
            bytes_io = io.BytesIO(content)
            bytes_io.seek(0)
            files = {"files": (file_path, bytes_io, "text/plain")}
            response = requests.post(url, files=files, **kwargs)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error uploading file to thread: {response.status_code} "
                f"{response.text}",
            ) from e
        return response

    def upload_file_to_agent(self, agent_id: str, file_path: str):
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/files")
        with open(file_path, "rb") as file:
            files = {"files": (os.path.basename(file_path), file, "text/plain")}
            response = requests.post(url, files=files)
        response.raise_for_status()
        return response

    def _upload_multiple_files(
        self,
        endpoint: Literal["threads", "agents"],
        owner_id: str,
        file_paths: list[str],
    ):
        url = urljoin(self.base_url + "/", f"{endpoint}/{owner_id}/files")
        files = [
            (
                "files",
                (os.path.basename(file_path), open(file_path, "rb"), "text/plain"),
            )
            for file_path in file_paths
        ]
        response = requests.post(url, files=files)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error uploading file to thread: {response.status_code} "
                f"{response.text}",
            ) from e
        return response

    def upload_files_to_thread(
        self,
        thread_id: str,
        thread_files: list[str],
    ) -> requests.models.Response:
        return self._upload_multiple_files("threads", thread_id, thread_files)

    def upload_files_to_agent(
        self,
        agent_id: str,
        agent_files: list[str],
    ) -> requests.models.Response:
        return self._upload_multiple_files("agents", agent_id, agent_files)
