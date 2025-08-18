import itertools
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Literal
from urllib.parse import urljoin

import requests

HEADER_INDEX = 0

DEBUG = True


@dataclass
class SecretKey:
    """
    Secret Key Definition.
    """

    value: str  # The key of the secret key.


@dataclass
class ActionPackage:
    """
    Action Package Definition.
    """

    name: str  # The name of the action package.
    organization: str  # The organization of the action package.
    version: str  # The version of the action package.
    url: str  # URL of the action server that hosts the action package.
    api_key: SecretKey  # API Key of the action server that hosts the action package.
    whitelist: str = ""  # Whitelist of actions (comma separated) accepted in the action package.
    allowed_actions: list[str] = field(default_factory=list)  # List of allowed actions.


def print_header(message):
    if DEBUG:
        global HEADER_INDEX  # noqa: PLW0603
        HEADER_INDEX += 1
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        header = f"[{timestamp}] {HEADER_INDEX}. {message}"
        print(f"\n{header}")
        print("-" * len(header))


def print_success(message):
    if DEBUG:
        print(f"SUCCESS: {message}")  # Green color


def print_error(message):
    if DEBUG:
        print(f"ERROR: {message}")  # Red color


def print_warning(message):
    if DEBUG:
        print(f"WARNING: {message}")  # Yellow color


def print_info(message):
    if DEBUG:
        print(f"INFO: {message}")  # Blue color


@dataclass
class AIMessage:
    """Represents a text message from the AI"""

    content: str

    def print_info(self):
        print_info(f"AI (text) message content: {self.content}")


@dataclass
class ToolCallMessage:
    """Represents a tool call event"""

    tool_name: str
    tool_call_id: str
    input_data: dict
    result: dict

    def print_info(self):
        print_info(f"Tool Call: {self.tool_name}")
        print_info(f"  Call ID: {self.tool_call_id}")
        for key, value in self.input_data.items():
            print_info(f"  {key}: {value}")
        print_info(f"  Result: {self.result}")


@dataclass
class ToolReturnMessage:
    """Represents a tool return event"""

    tool_name: str
    tool_call_id: str
    output_data: str | dict

    def print_info(self, limit: int = 300):
        print_info(f"Tool Return: {self.tool_name}")
        print_info(f"  Call ID: {self.tool_call_id}")
        if isinstance(self.output_data, str):
            print_info(
                f"  Output: '{self.output_data[:limit]}...'"
                if len(self.output_data) > limit
                else f"  Output: '{self.output_data}'"
            )
        elif isinstance(self.output_data, dict):
            for key, value in self.output_data.items():
                print_info(
                    f"  {key}: '{value[:limit]}...'"
                    if isinstance(value, str) and len(value) > limit
                    else f"  {key}: '{value}'"
                )


class ReceivedMessages:
    """Container for all messages received from the stream"""

    def __init__(self) -> None:
        self.ai_messages: list[AIMessage] = []
        self.tool_calls: list[ToolCallMessage] = []
        self.tool_returns: list[ToolReturnMessage] = []
        self.all_messages: list[AIMessage | ToolCallMessage | ToolReturnMessage] = []

    def get_final_ai_message(self) -> str | None:
        """Returns the content of the last AI message, if any"""
        if self.ai_messages:
            return self.ai_messages[-1].content
        return None

    def _on_append_message(self, message: AIMessage | ToolCallMessage | ToolReturnMessage):
        self.all_messages.append(message)

        if DEBUG:
            message.print_info()

    def append_ai_message(self, message: AIMessage):
        self.ai_messages.append(message)
        self._on_append_message(message)

    def append_tool_call(self, message: ToolCallMessage):
        self.tool_calls.append(message)
        self._on_append_message(message)

    def append_tool_return(self, message: ToolReturnMessage):
        self.tool_returns.append(message)
        self._on_append_message(message)

    def print_info(self):
        for message in self.all_messages:
            message.print_info()


def _send_message_collect_all_responses(
    base_url: str, agent_id: str, thread_id: str, message: str
) -> ReceivedMessages:
    """Sends a message to the specified thread and collects all response messages."""
    import json

    # We need to change to:
    # 1. Add message to the thread posting to: /threads/${tid}/messages
    # 2. Call /runs/${agent_id}/sync
    url = f"{base_url}/threads/{thread_id}/messages"
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "role": "user",
        "content": [
            {
                "kind": "text",
                "complete": False,
                "text": message,
            }
        ],
        "commited": False,
        "agent_metadata": {},
        "server_metadata": {},
    }

    response = requests.post(url, headers=headers, json=data)
    assert response.status_code == requests.codes.ok, (
        f"Error sending message: {response.status_code} {response.text}"
    )

    # Now 2:
    url = f"{base_url}/runs/{agent_id}/sync"
    sync_data = {
        "thread_id": thread_id,
        "agent_id": agent_id,
    }
    response = requests.post(url, headers=headers, json=sync_data)
    assert response.status_code == requests.codes.ok, (
        f"Error syncing run: {response.status_code} {response.text}"
    )

    received_messages = ReceivedMessages()

    response_data: list[dict] = response.json()
    for response_message in response_data:
        for content in response_message["content"]:
            if content["kind"] == "thought":
                continue

            elif content["kind"] == "text":
                received_messages.append_ai_message(AIMessage(content=content["text"]))

            elif content["kind"] == "tool_call":
                try:
                    result = json.loads(content["result"])
                except Exception:
                    # Workaround agent server bug: https://sema4ai.slack.com/archives/C06RN3M8CKX/p1747929153206069
                    result = content["result"]

                try:
                    input_data = json.loads(content["arguments_raw"])
                except Exception:
                    # Workaround agent server bug: https://sema4ai.slack.com/archives/C06RN3M8CKX/p1747929153206069
                    input_data = content["arguments_raw"]

                received_messages.append_tool_call(
                    ToolCallMessage(
                        tool_name=content["name"],
                        tool_call_id=content["tool_call_id"],
                        input_data=input_data,
                        result=result,
                    )
                )

            else:
                raise ValueError(f"Unknown content kind: {content['kind']}")

    if not received_messages.ai_messages:
        print_warning("\nNo AI response received.")

    return received_messages


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
        if response.status_code == requests.codes.no_content:
            print_success(f"Successfully deleted agent with ID: {agent_id}")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code} when deleting agent {agent_id}",
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
        if response.status_code == requests.codes.ok:
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
                    f"Error getting files from thread: {response.status_code} {response.text}",
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
        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error getting file by ref: {response.status_code} {response.text}",
                ) from e

    def get_file_by_ref(
        self,
        thread_id: str,
        file_ref: str,
        output_type: Literal["str", "bytes"] = "str",
    ) -> str | bytes:
        from pathlib import Path
        from urllib.parse import urlparse

        from sema4ai.common import uris

        file_info = self.get_file_info_by_ref(thread_id, file_ref)
        file_url = file_info.get("file_url") if file_info else None
        if not file_url:
            raise ValueError(
                f"file_url not available in response. Response: {file_info}",
            )

        parsed_url = urlparse(file_url)
        if parsed_url.scheme == "file":
            p = Path(uris.to_fs_path(file_url))
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
        if response.status_code == requests.codes.no_content:
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
        if response.status_code == requests.codes.no_content:
            print_success(f"Successfully deleted all files from thread {thread_id}")
        else:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise requests.exceptions.HTTPError(
                    f"Error deleting all files from thread: {response.status_code} {response.text}",
                ) from e

    def create_agent_and_return_agent_id(
        self,
        *,
        name: str = "",
        action_packages: list[ActionPackage] | None = None,
        runbook: str = "This is a test runbook",
        description: str = "This is a test agent",
        platform_configs: list[dict] | None = None,
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
            "platform_configs": platform_configs or [],
            "extra": {
                "test": "test",
            },
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == requests.codes.ok:
            agent_id = response.json()["agent_id"]
            assert agent_id is not None, "Agent id is None right after creation"
            print_success(f"Created agent with ID: {agent_id}")

            self._created_agent_ids.append(agent_id)
            return agent_id
        else:
            raise Exception(
                f"Error creating agent: {response.status_code} {response.text}",
            )

    def update_agent(self, agent_id: str, update_payload: dict):
        """Updates an agent."""
        url = urljoin(self.base_url + "/", f"agents/{agent_id}")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = requests.put(url, headers=headers, json=update_payload)
        if response.status_code == requests.codes.ok:
            print_success(f"Updated agent {agent_id}")
        else:
            raise Exception(
                f"Error updating agent {agent_id}: {response.status_code} {response.text}",
            )

    def create_agent_from_package_and_return_agent_id(
        self,
        *,
        name: str = "",
        agent_package_base64: str | None = None,
        platform_configs: list[dict] | None = None,
    ) -> str:
        """Creates an agent from a package and returns the agent ID."""
        url = urljoin(self.base_url + "/", "agents/package")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "name": name,
            "agent_package_base64": agent_package_base64,
            "model": {"provider": "openai", "name": "gpt-4o"},
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == requests.codes.ok:
            agent_id = response.json()["agent_id"]
            assert agent_id is not None, "Agent id is None right after creation"
            print_success(f"Created agent with ID: {agent_id}")
            # Right now, we're only using OpenAI.
            from agent_platform.core.platforms.openai import OpenAIPlatformParameters
            from agent_platform.core.utils import SecretString

            if platform_configs is not None:
                platform_config = OpenAIPlatformParameters(
                    openai_api_key=SecretString(platform_configs[0]["openai_api_key"]),
                ).model_dump()
                update_payload = {
                    "name": response.json()["name"],
                    "description": response.json()["description"],
                    "version": response.json()["version"],
                    "platform_configs": [platform_config],
                    "agent_architecture": {
                        "name": "agent_platform.architectures.default",
                        "version": "1.0.0",
                    },
                    "runbook": response.json()["runbook"],
                }
                self.update_agent(agent_id, update_payload)
            self._created_agent_ids.append(agent_id)

            return agent_id
        else:
            raise Exception(
                f"Error creating agent from package: {response.status_code} {response.text}",
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
        if response.status_code == requests.codes.ok:
            thread_id = response.json()["thread_id"]
        else:
            raise Exception(
                f"Error creating thread: {response.status_code} {response.text}",
            )

        assert thread_id is not None, "Thread id is None right after creation"
        print_success(f"Created thread with ID: {thread_id}")
        return thread_id

    # changed return type to tuple to access AI message text
    # and tool calls during msg handling

    def send_message_to_agent_thread(
        self, agent_id: str, thread_id: str, message: str = "question"
    ) -> tuple[str, list[ToolCallMessage]]:
        print_header("SENDING MESSAGE AND READING RESPONSE")
        print_info(f"Sending message: {message}")

        received_messages = _send_message_collect_all_responses(
            self.base_url, agent_id, thread_id, message
        )
        final_message = received_messages.get_final_ai_message()
        assert final_message is not None, "No AI message received in response"
        return final_message, received_messages.tool_calls

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
                f"Error uploading file to thread: {response.status_code} {response.text}",
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
                f"Error uploading file to thread: {response.status_code} {response.text}",
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

    def get_agent_details(self, agent_id: str) -> dict:
        """
        Gets the details of an agent including its runbook and action package statuses.

        Args:
            agent_id: The ID of the agent to get details for.

        Returns:
            A dictionary containing the agent details with runbook and action package information.

        Raises:
            HTTPError: If the agent details could not be retrieved.
        """
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/agent-details")
        response = requests.get(url)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting agent details: {response.status_code} {response.text}",
            ) from e

    def inspect_file_as_data_frame(
        self,
        thread_id: str,
        file_id: str,
        num_samples: int = 5,
    ) -> list[dict]:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/inspect-file-as-data-frame")
        response = requests.get(url, params={"file_id": file_id, "num_samples": num_samples})
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error inspecting file as data frame: {response.status_code} {response.text}",
            ) from e

    def create_data_frame_from_file(
        self,
        thread_id: str,
        file_id: str,
        sheet_name: str | None = None,
        name: str | None = None,
    ) -> dict:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames/from-file")
        params = {"file_id": file_id}
        if sheet_name is not None:
            params["sheet_name"] = sheet_name
        if name is not None:
            params["name"] = name
        response = requests.post(url, params=params)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error creating data frame: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def get_data_frames(self, thread_id: str) -> list[dict]:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting data frames: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def create_data_frame_from_sql_computation(
        self,
        thread_id: str,
        name: str,
        sql_query: str,
        description: str | None = None,
        sql_dialect: str = "duckdb",
    ) -> dict:
        """Create a new data frame from existing data frames using a SQL computation.

        Args:
            thread_id: The ID of the thread
            name: The name for the new data frame
            sql_query: The SQL query to execute
            input_data_frames: Dictionary mapping table names to data frame IDs
            description: Optional description for the new data frame
            sql_dialect: The dialect of the SQL query to use (default is "duckdb")

        Returns:
            The created data frame information
        """
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames/from-computation")
        payload = {
            "new_data_frame_name": name,
            "sql_query": sql_query,
            "sql_dialect": sql_dialect,
        }
        if description is not None:
            payload["description"] = description

        response = requests.post(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error creating data frame from computation: {response.status_code} "
                f"{response.text}",
            ) from e
        return response.json()
