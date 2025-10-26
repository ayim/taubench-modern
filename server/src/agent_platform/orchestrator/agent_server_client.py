import itertools
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Any, Literal, TypedDict
from urllib.parse import urljoin

import requests
from sema4ai_docint.extraction.reducto.async_ import JobType

from agent_platform.core.payloads.document_intelligence import ExtractDocumentPayload
from agent_platform.core.payloads.document_intelligence_config import (
    DocumentIntelligenceConfigPayload,
)

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
    error: str | None

    def print_info(self):
        print_info(f"Tool Call: {self.tool_name}")
        print_info(f"  Call ID: {self.tool_call_id}")
        for key, value in self.input_data.items():
            print_info(f"  {key}: {value}")
        print_info(f"  Error: {self.error}")
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
                        error=content.get("error", None),
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

    def create_agent_and_return_agent_id(  # noqa: PLR0913
        self,
        *,
        name: str = "",
        action_packages: list[ActionPackage] | None = None,
        runbook: str = "This is a test runbook",
        description: str = "This is a test agent",
        platform_configs: list[dict] | None = None,
        document_intelligence: str | None = None,
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

        if document_intelligence:
            data["document_intelligence"] = document_intelligence

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
        num_samples: int = 5,
        *,
        file_id: str | None = None,
        file_ref: str | None = None,
    ) -> list[dict]:
        if file_id is not None and file_ref is not None:
            raise ValueError("Either file_id or file_ref must be provided, not both.")
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/inspect-file-as-data-frame")
        params = {}
        if file_id is not None:
            params["file_id"] = file_id
        if file_ref is not None:
            params["file_ref"] = file_ref
        if num_samples is not None:
            params["num_samples"] = num_samples
        response = requests.get(url, params=params)
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

    def get_data_frames(self, thread_id: str, num_samples: int = 0) -> list[dict]:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames")
        response = requests.get(url, params={"num_samples": num_samples})
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

    def get_data_frame_slice(  # noqa: PLR0913
        self,
        thread_id: str,
        data_frame_id: str,
        offset: int | None = None,
        limit: int | None = None,
        column_names: list[str] | None = None,
        output_format: Literal["json", "parquet"] = "json",
        order_by: str | None = None,
    ) -> bytes:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames/slice")
        params: dict[str, Any] = {"data_frame_id": data_frame_id}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if column_names is not None:
            params["column_names"] = column_names
        if output_format is not None:
            params["output_format"] = output_format
        if order_by is not None:
            params["order_by"] = order_by
        response = requests.post(url, json=params)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting data frame slice: {response.status_code} {response.text}",
            ) from e
        return response.content

    def get_data_frame_contents(  # noqa: PLR0913
        self,
        thread_id: str,
        data_frame_name: str,
        offset: int | None = None,
        limit: int | None = None,
        column_names: list[str] | None = None,
        output_format: Literal["json", "parquet"] = "json",
        order_by: str | None = None,
    ) -> bytes:
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/data-frames/{data_frame_name}")
        params: dict[str, Any] = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if column_names is not None:
            params["column_names"] = ",".join(column_names)
        if output_format is not None:
            params["output_format"] = output_format
        if order_by is not None:
            params["order_by"] = order_by
        response = requests.get(url, params=params)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting data frame contents: {response.status_code} {response.text}",
            ) from e
        return response.content

    def add_data_source_to_thread(
        self, thread_id: str, data_source_name: str, engine: str, connection_data: dict
    ) -> dict:
        url = urljoin(self.base_url + "/", f"/threads/{thread_id}/data-sources")
        payload = {
            "data_source_name": data_source_name,
            "engine": engine,
            "connection_data": connection_data,
        }
        response = requests.post(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error adding data source to thread: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def clear_document_intelligence(self):
        """Clear the Document Intelligence configuration."""
        url = urljoin(self.base_url + "/", "document-intelligence")
        response = requests.delete(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error clearing document intelligence: {response.status_code} {response.text}",
            ) from e
        return response

    def configure_document_intelligence(self, doc_int_config: DocumentIntelligenceConfigPayload):
        url = urljoin(self.base_url + "/", "document-intelligence")

        # Convert SecretString objects to plain strings before calling asdict
        from agent_platform.core.payloads.document_intelligence_config import IntegrationInput
        from agent_platform.core.utils import SecretString

        # Create new integrations with converted SecretString objects
        new_integrations = []
        if hasattr(doc_int_config, "integrations"):
            for integration in doc_int_config.integrations:
                if hasattr(integration, "api_key") and isinstance(
                    integration.api_key, SecretString
                ):
                    # Create a new IntegrationInput with the plain string API key
                    new_integration = IntegrationInput(
                        type=integration.type,
                        endpoint=integration.endpoint,
                        api_key=integration.api_key.get_secret_value(),
                        external_id=integration.external_id,
                    )
                    new_integrations.append(new_integration)
                else:
                    new_integrations.append(integration)

        # Create a new config with the converted integrations
        if new_integrations:
            config_copy = DocumentIntelligenceConfigPayload(
                data_server=doc_int_config.data_server,
                integrations=new_integrations,
                data_connections=doc_int_config.data_connections,
                data_connection_id=doc_int_config.data_connection_id,
            )
        else:
            config_copy = doc_int_config

        # Now convert to dict - SecretString objects are already converted
        config_dict = asdict(config_copy)

        response = requests.post(url, json=config_dict)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error configuring document intelligence: {response.status_code} {response.text}",
            ) from e
        return response

    def generate_extraction_schema(self, file_ref: str, thread_id: str, agent_id: str) -> dict:
        url = urljoin(
            self.base_url + "/",
            f"document-intelligence/documents/generate-schema?thread_id={thread_id}&agent_id={agent_id}",
        )

        headers = {
            "Accept": "application/json",
        }

        response = requests.post(url, headers=headers, data={"file": file_ref})

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error generating extraction schema: {response.status_code} {response.text}",
            ) from e
        result = response.json()
        print_success("Extraction schema generated successfully")
        return result

    def parse_document(self, file_ref: str, thread_id: str) -> dict:
        """Parse a document using Document Intelligence.

        Args:
            file_ref: Reference to the file that already exists in the thread
            thread_id: ID of the thread containing the file

        Returns:
            The parsed document result
        """
        url = urljoin(
            self.base_url + "/",
            f"document-intelligence/documents/parse?thread_id={thread_id}",
        )
        headers = {
            "Accept": "application/json",
        }

        response = requests.post(url, headers=headers, data={"file": file_ref})
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error parsing document: {response.status_code} {response.text}",
            ) from e
        result = response.json()
        print_success("Document parsed successfully")
        return result

    def start_async_document_parse(self, file_ref: str, thread_id: str) -> dict:
        url = urljoin(
            self.base_url + "/",
            f"document-intelligence/documents/parse/async?thread_id={thread_id}",
        )
        headers = {
            "Accept": "application/json",
        }
        response = requests.post(url, headers=headers, data={"file": file_ref})
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error starting document parse job: {response.status_code} {response.text}",
            ) from e
        result = response.json()
        print_success("Document parse job started successfully")
        return result

    def extract_document(self, extract_request: ExtractDocumentPayload) -> dict:
        url = urljoin(
            self.base_url + "/",
            "document-intelligence/documents/extract",
        )
        headers = {
            "Accept": "application/json",
        }
        payload = asdict(extract_request)
        extraction_schema = payload.get("document_layout", {}).get("extraction_schema")
        if extraction_schema is not None:
            payload["document_layout"]["extraction_schema"] = extraction_schema.model_dump(
                mode="json", exclude_none=True
            )
        response = requests.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error extracting document: {response.status_code} {response.text}",
            ) from e
        result = response.json()
        print_success("Document extracted successfully")
        return result

    def start_async_document_extract(self, extract_request: ExtractDocumentPayload) -> dict:
        url = urljoin(
            self.base_url + "/",
            "document-intelligence/documents/extract/async",
        )
        headers = {
            "Accept": "application/json",
        }
        response = requests.post(url, headers=headers, json=asdict(extract_request))
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error starting document extract job: {response.status_code} {response.text}",
            ) from e
        result = response.json()
        print_success("Document extract job started successfully")
        return result

    # Job status and result
    def get_job_status(self, job_id: str, job_type: JobType) -> dict:
        url = urljoin(
            self.base_url + "/",
            f"document-intelligence/jobs/{job_id}/status?job_type={job_type.value}",
        )
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting job status: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def get_job_result(self, job_id: str, job_type: JobType) -> dict:
        url = urljoin(
            self.base_url + "/",
            f"document-intelligence/jobs/{job_id}/result?job_type={job_type.value}",
        )
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting job result: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def create_data_connection(
        self, name: str, description: str, engine: str, configuration: dict
    ) -> dict:
        url = urljoin(self.base_url + "/", "/api/v2/data-connections")
        payload = {
            "name": name,
            "description": description,
            "engine": engine,
            "configuration": configuration,
        }
        response = requests.post(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error creating data connection: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def set_agent_data_connections(self, agent_id: str, data_connection_ids: list[str]) -> None:
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/data-connections")
        payload = {
            "data_connection_ids": data_connection_ids,
        }
        response = requests.put(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error setting agent data connections: {response.status_code} {response.text}",
            ) from e

    def get_agent_data_connections(self, agent_id: str) -> list[dict]:
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/data-connections")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting agent data connections: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def create_semantic_data_model(self, semantic_model: dict) -> dict:
        """Create a new semantic data model."""
        url = urljoin(self.base_url + "/", "semantic-data-models/")
        response = requests.post(url, json=semantic_model)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error creating semantic data model: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def set_semantic_data_model(
        self,
        semantic_data_model_id: str,
        semantic_model: dict,
    ) -> dict:
        """Set/update a semantic data model."""
        url = urljoin(self.base_url + "/", f"semantic-data-models/{semantic_data_model_id}")
        response = requests.put(url, json=semantic_model)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error setting semantic data model: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def get_semantic_data_model(self, semantic_data_model_id: str) -> dict:
        """Get a semantic data model by ID."""
        url = urljoin(self.base_url + "/", f"semantic-data-models/{semantic_data_model_id}")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting semantic data model: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def delete_semantic_data_model(self, semantic_data_model_id: str) -> None:
        """Delete a semantic data model by ID."""
        url = urljoin(self.base_url + "/", f"semantic-data-models/{semantic_data_model_id}")
        response = requests.delete(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error deleting semantic data model: {response.status_code} {response.text}",
            ) from e

    def generate_semantic_data_model(self, payload: dict) -> dict:
        """Generate a semantic data model from data connections and files."""
        url = urljoin(self.base_url + "/", "semantic-data-models/generate")
        response = requests.post(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error generating semantic data model: {response.status_code} {response.text}",
            ) from e
        return response.json()

    class TableToInspectTypedDict(TypedDict):
        name: str
        database: str | None
        schema: str | None
        # If the columns are passed, inspect only those columns, if not passed, inspect all columns
        columns_to_inspect: list[str] | None

    def inspect_data_connection(
        self,
        connection_id: str,
        tables_to_inspect: "list[TableToInspectTypedDict] | None" = None,
        inspect_columns: bool = True,
        n_sample_rows: int = 5,
    ) -> dict:
        """Inspect a data connection to get tables, columns and sample data."""
        url = urljoin(self.base_url + "/", f"data-connections/{connection_id}/inspect")
        response = requests.post(
            url,
            json={
                "tables_to_inspect": tables_to_inspect,
                "inspect_columns": inspect_columns,
                "n_sample_rows": n_sample_rows,
            },
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error inspecting data connection: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def inspect_file_as_data_connection(
        self,
        file_contents: bytes,
        file_name: str,
    ) -> dict:
        """Inspect a file to get tables, columns and sample data as if it were a data connection."""
        url = urljoin(self.base_url + "/", "data-connections/inspect-file-as-data-connection")
        headers = {
            "X-File-Name": file_name,
            "Content-Type": "application/octet-stream",
        }
        response = requests.post(url, data=file_contents, headers=headers)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error inspecting file as data connection: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def set_thread_semantic_data_models(
        self, thread_id: str, semantic_data_model_ids: list[str]
    ) -> None:
        """Set the semantic data models for a thread."""
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/semantic-data-models")
        payload = {
            "semantic_data_model_ids": semantic_data_model_ids,
        }
        response = requests.put(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error setting thread semantic data models: "
                f"{response.status_code} {response.text}",
            ) from e

    def get_thread_semantic_data_models(self, thread_id: str) -> list[dict]:
        """Get the semantic data models for a thread."""
        url = urljoin(self.base_url + "/", f"threads/{thread_id}/semantic-data-models")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting thread semantic data models: "
                f"{response.status_code} {response.text}",
            ) from e
        return response.json()

    def set_agent_semantic_data_models(
        self, agent_id: str, semantic_data_model_ids: list[str]
    ) -> None:
        """Set the semantic data models for an agent."""
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/semantic-data-models")
        payload = {
            "semantic_data_model_ids": semantic_data_model_ids,
        }
        response = requests.put(url, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error setting agent semantic data models: {response.status_code} {response.text}",
            ) from e

    def get_agent_semantic_data_models(self, agent_id: str) -> list[dict]:
        """Get the semantic data models for an agent."""
        url = urljoin(self.base_url + "/", f"agents/{agent_id}/semantic-data-models")
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error getting agent semantic data models: {response.status_code} {response.text}",
            ) from e
        return response.json()

    def list_semantic_data_models(
        self, agent_id: str | None = None, thread_id: str | None = None
    ) -> list[dict]:
        """List semantic data models with optional filtering by agent_id or thread_id."""
        url = urljoin(self.base_url + "/", "semantic-data-models/")
        params = {}
        if agent_id is not None:
            params["agent_id"] = agent_id
        if thread_id is not None:
            params["thread_id"] = thread_id

        response = requests.get(url, params=params)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"Error listing semantic data models: {response.status_code} {response.text}",
            ) from e
        return response.json()
