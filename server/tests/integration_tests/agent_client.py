import itertools
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Literal, TypedDict

import requests
import sema4ai_http
from agent_server_types import (
    DEFAULT_ARCHITECTURE,
    RAW_CONTEXT,
    AgentAdvancedConfig,
    AgentMetadata,
    AgentMode,
    AgentReasoning,
    AgentStatus,
    LLMProvider,
    OpenAIGPT,
    OpenAIGPTConfig,
)
from fastapi import status

from tests.integration_tests.integration_fixtures import assert_status

HEADER_INDEX = 0

DEBUG = True


def print_header(message):
    if DEBUG:
        global HEADER_INDEX
        HEADER_INDEX += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
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


@dataclass
class ActionPackageDataClass:
    """
    Action Package Definition.
    """

    name: str  # The name of the action package.
    organization: str  # The organization of the action package.
    version: str  # The version of the action package.
    url: str  # URL of the action server that hosts the action package.
    api_key: str  # API Key of the action server that hosts the action package.
    whitelist: str = ""  # Whitelist of actions (comma separated) that are accepted in the action package.


@dataclass
class AIMessage:
    """Represents a message from the AI"""

    content: str

    # Note: there may be other finish reasons not listed here
    finish_reason: Literal["stop"] | None = None

    def is_final(self) -> bool:
        return self.finish_reason is not None

    def print_info(self):
        print_info(
            f"AI Message:\n  finish_reason: {self.finish_reason}\n  content: {self.content}",
        )


@dataclass
class ToolCallMessage:
    """Represents a tool call event"""

    tool_name: str
    tool_call_id: str
    input_data: dict

    def print_info(self):
        print_info(f"Tool Call: {self.tool_name}")
        print_info(f"  Call ID: {self.tool_call_id}")
        for key, value in self.input_data.items():
            print_info(f"  {key}: {value}")


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
                else f"  Output: '{self.output_data}'",
            )
        elif isinstance(self.output_data, dict):
            for key, value in self.output_data.items():
                print_info(
                    f"  {key}: '{value[:limit]}...'"
                    if isinstance(value, str) and len(value) > limit
                    else f"  {key}: '{value}'",
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

    def _on_append_message(
        self,
        message: AIMessage | ToolCallMessage | ToolReturnMessage,
    ):
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
    base_url: str,
    thread_id: str,
    message: str,
) -> ReceivedMessages:
    """Sends a message to the specified thread and collects all response messages."""
    url = f"{base_url}/runs/stream"
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    data = {
        "input": [
            {
                "content": message,
                "type": "human",
                "example": False,
            },
        ],
        "thread_id": thread_id,
    }

    response = requests.post(url, headers=headers, json=data, stream=True)
    assert (
        response.status_code == 200
    ), f"Error sending message: {response.status_code} {response.text}"

    received_messages = ReceivedMessages()

    for line in response.iter_lines():
        if line:
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                data = json.loads(decoded_line[6:])
                if isinstance(data, list) and len(data) > 0:
                    message_part = data[-1]
                    if message_part["type"] == "ai":
                        finish_reason = message_part.get("response_metadata", {}).get(
                            "finish_reason",
                        )
                        ai_message = AIMessage(
                            content=message_part["content"],
                            finish_reason=finish_reason,
                        )
                        if ai_message.is_final():
                            received_messages.append_ai_message(ai_message)
                        elif DEBUG:
                            print(".", end="", flush=True)

                    elif message_part["type"] == "tool_event":
                        tool_name = message_part.get("name", "Unknown tool")
                        tool_call_id = message_part.get("tool_call_id", "N/A")
                        input_data = message_part.get("input", {})
                        output_data = message_part.get("output")

                        if output_data is None:
                            # This is a tool call
                            received_messages.append_tool_call(
                                ToolCallMessage(
                                    tool_name=tool_name,
                                    tool_call_id=tool_call_id,
                                    input_data=input_data,
                                ),
                            )
                        else:
                            # This is a tool return
                            received_messages.append_tool_return(
                                ToolReturnMessage(
                                    tool_name=tool_name,
                                    tool_call_id=tool_call_id,
                                    output_data=output_data,
                                ),
                            )

    if not received_messages.ai_messages:
        print_warning("\nNo AI response received.")

    return received_messages


class FileByRefResponseTypedDict(TypedDict):
    file_url: str


class ThreadStateTypedDict(TypedDict):
    full_state: dict
    last_ai_message: dict | None


class StatusResponseTypedDict(TypedDict):
    status: str


class AsyncRunResponseTypedDict(TypedDict):
    run_id: str


class AgentServerClient:
    """
    A client for interacting with the agent server.
    """

    def __init__(self, base_url: str):
        """
        Args:
            base_url: The base URL of the agent server.
        """

        if not base_url.endswith("/api/v1"):
            base_url = f"{base_url}/api/v1"
        self.base_url = base_url
        self._created_agent_ids: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.remove_created_agents()

    def delete_agent(self, agent_id: str):
        """Delete an agent by ID."""
        url = f"{self.base_url}/agents/{agent_id}"
        response = requests.delete(url)
        if response.status_code == status.HTTP_200_OK:
            print_success(f"Successfully deleted agent with ID: {agent_id}")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code} when deleting agent {agent_id}",
            )

    def remove_created_agents(self):
        """Removes all agents that were created by the client."""
        for agent_id in self._created_agent_ids:
            self.delete_agent(agent_id)

    def list_files(self, thread_id: str) -> set[str]:
        """
        Lists all files in the specified thread.

        Returns: A set of file references.
        """
        base_url_api = f"{self.base_url}"
        url = f"{base_url_api}/threads/{thread_id}/files"
        headers = {
            "Content-Type": "application/json",
        }
        response = sema4ai_http.get(url, headers=headers)
        assert response.status == 200
        response_data = response.json()
        file_refs = set()
        for entry in response_data:
            file_refs.add(entry["file_ref"])
        return file_refs

    def get_file_info_by_ref(
        self,
        thread_id: str,
        file_ref: str,
    ) -> FileByRefResponseTypedDict:
        """Retrieves a file using the new get-file endpoint."""
        url = f"{self.base_url}/threads/{thread_id}/file-by-ref"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        params = {"file_ref": file_ref}

        response = sema4ai_http.get(url, headers=headers, fields=params)
        assert_status(response, f"Error retrieving file: {url}.")
        return response.json()

    def get_file_by_ref(
        self,
        thread_id: str,
        file_ref: str,
        output_type: Literal["str", "bytes"] = "str",
    ) -> str | bytes:
        import urllib
        from pathlib import Path

        from sema4ai_agent_server.file_manager.local import url_to_fs_path

        file_info = self.get_file_info_by_ref(thread_id, file_ref)
        file_url = file_info.get("file_url")
        if not file_url:
            raise ValueError(
                f"file_url not available in response. " f"Response: {file_info}",
            )

        parsed_url = urllib.parse.urlparse(file_url)
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

    _next_agent_id = partial(next, itertools.count())

    def create_agent_and_return_agent_id(
        self,
        openai_api_key: str,
        *,
        name: str = "",
        architecture=DEFAULT_ARCHITECTURE,
        action_packages: Sequence[ActionPackageDataClass] = (),
        runbook: str = "This is a test runbook",
        description: str = "This is a test agent",
        wait_for_ready: bool = True,
    ) -> str:
        print_header("CREATING AGENT")

        from dataclasses import asdict

        model = OpenAIGPT(
            provider=LLMProvider.OPENAI,
            name="gpt-3.5-turbo",
            config=OpenAIGPTConfig(temperature=0.0, openai_api_key=openai_api_key),
        )
        metadata = AgentMetadata(mode=AgentMode.CONVERSATIONAL)
        advanced_config = AgentAdvancedConfig(
            architecture=architecture,
            reasoning=AgentReasoning.DISABLED,
        )
        url = f"{self.base_url}/agents"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not name:
            name = f"Test Agent {self._next_agent_id()}"

        action_packages_raw: list[dict] = [asdict(ap) for ap in action_packages]
        data = {
            "public": True,
            "name": name,
            "description": description,
            "runbook": runbook,
            "version": "0.0.1",
            "model": model.model_dump(mode="json", context=RAW_CONTEXT),
            "advanced_config": advanced_config.model_dump(
                mode="json",
                context=RAW_CONTEXT,
            ),
            "action_packages": action_packages_raw,
            "metadata": metadata.model_dump(mode="json", context=RAW_CONTEXT),
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == status.HTTP_200_OK:
            agent_id = response.json()["id"]
            assert agent_id is not None, "Agent id is None right after creation"
            print_success(f"Created agent with ID: {agent_id}")

            self._created_agent_ids.append(agent_id)
            if wait_for_ready:
                self.wait_for_agent_readiness(agent_id)
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
        url = f"{self.base_url}/threads"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "agent_id": agent_id,
            "name": "Welcome",
            "starting_message": "Hello! I am a Sema4.ai Agent, here to assist you with a wide range of tasks. I can help you with:\n\n1. **Information Retrieval**: Providing accurate and up-to-date information on a variety of topics.\n2. **Task Automation**: Assisting with repetitive tasks, scheduling, and reminders.\n3. **Data Analysis**: Analyzing data and generating reports.\n4. **Technical Support**: Offering troubleshooting and technical assistance.\n5. **Content Creation**: Helping with writing, editing, and generating content.\n6. **Learning and Development**: Providing educational resources and personalized learning plans.\n\nFeel free to ask me anything, and I'll do my best to assist you!",
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

    def send_message_to_agent_thread(
        self,
        thread_id: str,
        message: str = "question",
    ) -> str:
        print_header("SENDING MESSAGE AND STREAMING RESPONSE")
        print_info(f"Sending message: {message}")

        received_messages = _send_message_collect_all_responses(
            self.base_url,
            thread_id,
            message,
        )
        final_message = received_messages.get_final_ai_message()
        assert final_message is not None, "No AI message received in response"
        return final_message

    def send_message_to_agent_thread_collect_all(
        self,
        thread_id: str,
        message: str = "question",
    ) -> ReceivedMessages:
        return _send_message_collect_all_responses(self.base_url, thread_id, message)

    def create_async_run(
        self,
        thread_id: str,
        message: str,
    ) -> AsyncRunResponseTypedDict:
        """Creates an asynchronous run for the specified thread."""
        url = f"{self.base_url}/runs/async_invoke"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "thread_id": thread_id,
            "input": [{"content": message, "type": "human", "example": False}],
        }

        response = sema4ai_http.post(url, headers=headers, json=data)
        assert_status(response, f"Error creating async run for {url}.")
        result = response.json()
        assert result, f"Async run creation failed. Response: {result!r}"
        return result

    def get_thread_state(self, thread_id: str) -> ThreadStateTypedDict:
        """Retrieves the state of the specified thread and extracts the last AI message."""
        url = f"{self.base_url}/threads/{thread_id}/state"
        headers = {
            "Accept": "application/json",
        }

        response = sema4ai_http.get(url, headers=headers)
        assert_status(response, f"Error retrieving thread state for {url}.")

        state = response.json()
        messages = state["values"]["messages"]
        ai_messages = [msg for msg in messages if msg["type"] == "ai"]
        last_ai_message = ai_messages[-1] if ai_messages else None
        return {"full_state": state, "last_ai_message": last_ai_message}

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

        url = f"{self.base_url}/threads/{thread_id}/files"
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
        url = f"{self.base_url}/agents/{agent_id}/files"
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
        url = f"{self.base_url}/{endpoint}/{owner_id}/files"
        files = [
            (
                "files",
                (os.path.basename(file_path), open(file_path, "rb"), "text/plain"),
            )
            for file_path in file_paths
        ]
        response = requests.post(url, files=files)
        response.raise_for_status()
        return response

    def upload_files_to_thread(self, thread_id: str, thread_files: list[str]) -> None:
        return self._upload_multiple_files("threads", thread_id, thread_files)

    def upload_files_to_agent(self, agent_id: str, agent_files: list[str]) -> None:
        return self._upload_multiple_files("agents", agent_id, agent_files)

    def get_agent_status(self, agent_id: str) -> AgentStatus:
        url = f"{self.base_url}/agents/{agent_id}/status"
        response = sema4ai_http.get(url)
        assert_status(response, f"Error retrieving agent status for {url}.")
        return AgentStatus.model_validate(response.json())

    def get_run_status(self, run_id: str) -> StatusResponseTypedDict:
        """Retrieves the status of an asynchronous run."""
        url = f"{self.base_url}/runs/{run_id}/status"
        headers = {
            "Accept": "application/json",
        }

        response = sema4ai_http.get(url, headers=headers)
        assert_status(response, f"Error retrieving run status for {url}.")
        return response.json()

    def wait_for_agent_readiness(self, agent_id: str, timeout=20):
        print_header("WAITING FOR AGENT READINESS")
        start_time = time.time()

        while True:
            status = self.get_agent_status(agent_id)
            if status.ready:
                print_success("Agent is ready")
                return

            if time.time() - start_time > timeout:
                issues = status.issues
                raise TimeoutError(
                    f"Agent {agent_id} did not become ready within {timeout} seconds. {issues}",
                )

            time.sleep(0.25)

    def get_openapi_schema(self) -> dict:
        url = f"{self.base_url}/openapi.json"
        print_info(f"Fetching OpenAPI schema from {url}")

        response = sema4ai_http.get(url)
        assert_status(response, f"Error fetching OpenAPI schema from {url}.")
        return response.json()


class AgentServerClientV2:
    """
    A client for interacting with the agent server.
    """

    def __init__(self, base_url: str):
        """
        Args:
            base_url: The base URL of the agent server.
        """

        if not base_url.endswith("/api/v2"):
            base_url = f"{base_url}/api/v2"
        self.base_url = base_url
        self._created_agent_ids: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.remove_created_agents()

    def delete_agent(self, agent_id: str):
        """Delete an agent by ID."""
        url = f"{self.base_url}/agents/{agent_id}"
        response = requests.delete(url)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            print_success(f"Successfully deleted agent with ID: {agent_id}")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code} when deleting agent {agent_id}",
            )

    def remove_created_agents(self):
        """Removes all agents that were created by the client."""
        for agent_id in self._created_agent_ids:
            self.delete_agent(agent_id)

    def list_files(self, thread_id: str) -> set[str]:
        """
        Lists all files in the specified thread.

        Returns: A set of file references.
        """
        base_url_api = f"{self.base_url}"
        url = f"{base_url_api}/threads/{thread_id}/files"
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
                    f"Error getting files from thread: {response.status_code} {response.text}",
                ) from e

    def get_file_info_by_ref(
        self,
        thread_id: str,
        file_ref: str,
    ) -> FileByRefResponseTypedDict:
        """Retrieves a file using the new get-file endpoint."""
        url = f"{self.base_url}/threads/{thread_id}/file-by-ref"
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
                    f"Error getting file by ref: {response.status_code} {response.text}",
                ) from e

    def get_file_by_ref(
        self,
        thread_id: str,
        file_ref: str,
        output_type: Literal["str", "bytes"] = "str",
    ) -> str | bytes:
        import urllib
        from pathlib import Path

        from sema4ai_agent_server.file_manager.local import url_to_fs_path

        file_info = self.get_file_info_by_ref(thread_id, file_ref)
        file_url = file_info.get("file_url")
        if not file_url:
            raise ValueError(
                f"file_url not available in response. " f"Response: {file_info}",
            )

        parsed_url = urllib.parse.urlparse(file_url)
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

    _next_agent_id = partial(next, itertools.count())

    def delete_file_by_ref(self, thread_id: str, file_ref: str) -> None:
        url = f"{self.base_url}/threads/{thread_id}/files/{file_ref}"
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
                    f"Error deleting file {file_ref} from thread {thread_id}: {response.status_code} {response.text}",
                ) from e

    def delete_all_files_from_thread(self, thread_id: str) -> None:
        url = f"{self.base_url}/threads/{thread_id}/files"
        response = requests.delete(url)
        if response.status_code == status.HTTP_204_NO_CONTENT:
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
        openai_api_key: str,
        *,
        name: str = "",
        architecture="agent_architecture_default_v2",
        action_packages: Sequence[ActionPackageDataClass] = (),
        runbook: str = "This is a test runbook",
        description: str = "This is a test agent",
        wait_for_ready: bool = False,
    ) -> str:
        print_header("CREATING AGENT")

        from dataclasses import asdict

        url = f"{self.base_url}/agents"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not name:
            name = f"Test Agent {self._next_agent_id()}"

        action_packages_raw: list[dict] = [asdict(ap) for ap in action_packages]
        data = {
            "mode": "conversational",
            "name": name,
            "version": "1.0.0",
            "description": description,
            "runbook_raw_text": runbook,
            "action_packages": action_packages_raw,
            "agent_architecture": {
                "name": "agent_architecture_default_v2",
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
            if wait_for_ready:
                self.wait_for_agent_readiness(agent_id)
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
        url = f"{self.base_url}/threads"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "agent_id": agent_id,
            "name": "Welcome",
            "starting_message": "Hello! I am a Sema4.ai Agent, here to assist you with a wide range of tasks. I can help you with:\n\n1. **Information Retrieval**: Providing accurate and up-to-date information on a variety of topics.\n2. **Task Automation**: Assisting with repetitive tasks, scheduling, and reminders.\n3. **Data Analysis**: Analyzing data and generating reports.\n4. **Technical Support**: Offering troubleshooting and technical assistance.\n5. **Content Creation**: Helping with writing, editing, and generating content.\n6. **Learning and Development**: Providing educational resources and personalized learning plans.\n\nFeel free to ask me anything, and I'll do my best to assist you!",
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

    def send_message_to_agent_thread(
        self,
        thread_id: str,
        message: str = "question",
    ) -> str:
        print_header("SENDING MESSAGE AND STREAMING RESPONSE")
        print_info(f"Sending message: {message}")

        received_messages = _send_message_collect_all_responses(
            self.base_url,
            thread_id,
            message,
        )
        final_message = received_messages.get_final_ai_message()
        assert final_message is not None, "No AI message received in response"
        return final_message

    def send_message_to_agent_thread_collect_all(
        self,
        thread_id: str,
        message: str = "question",
    ) -> ReceivedMessages:
        return _send_message_collect_all_responses(self.base_url, thread_id, message)

    def create_async_run(
        self,
        thread_id: str,
        message: str,
    ) -> AsyncRunResponseTypedDict:
        """Creates an asynchronous run for the specified thread."""
        url = f"{self.base_url}/runs/async_invoke"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "thread_id": thread_id,
            "input": [{"content": message, "type": "human", "example": False}],
        }

        response = sema4ai_http.post(url, headers=headers, json=data)
        assert_status(response, f"Error creating async run for {url}.")
        result = response.json()
        assert result, f"Async run creation failed. Response: {result!r}"
        return result

    def get_thread_state(self, thread_id: str) -> ThreadStateTypedDict:
        """Retrieves the state of the specified thread and extracts the last AI message."""
        url = f"{self.base_url}/threads/{thread_id}/state"
        headers = {
            "Accept": "application/json",
        }

        response = sema4ai_http.get(url, headers=headers)
        assert_status(response, f"Error retrieving thread state for {url}.")

        state = response.json()
        messages = state["values"]["messages"]
        ai_messages = [msg for msg in messages if msg["type"] == "ai"]
        last_ai_message = ai_messages[-1] if ai_messages else None
        return {"full_state": state, "last_ai_message": last_ai_message}

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

        url = f"{self.base_url}/threads/{thread_id}/files"
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
        url = f"{self.base_url}/agents/{agent_id}/files"
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
        url = f"{self.base_url}/{endpoint}/{owner_id}/files"
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

    def upload_files_to_thread(self, thread_id: str, thread_files: list[str]) -> None:
        return self._upload_multiple_files("threads", thread_id, thread_files)

    def upload_files_to_agent(self, agent_id: str, agent_files: list[str]) -> None:
        return self._upload_multiple_files("agents", agent_id, agent_files)

    def get_agent_status(self, agent_id: str) -> AgentStatus:
        raise NotImplementedError("Not implemented as status API does not exist")

    def get_run_status(self, run_id: str) -> StatusResponseTypedDict:
        """Retrieves the status of an asynchronous run."""
        url = f"{self.base_url}/runs/{run_id}/status"
        headers = {
            "Accept": "application/json",
        }

        response = sema4ai_http.get(url, headers=headers)
        assert_status(response, f"Error retrieving run status for {url}.")
        return response.json()

    def wait_for_agent_readiness(self, agent_id: str, timeout=20):
        raise NotImplementedError("Not implemented as status API does not exist")

    def get_openapi_schema(self) -> dict:
        url = f"{self.base_url}/openapi.json"
        print_info(f"Fetching OpenAPI schema from {url}")

        response = sema4ai_http.get(url)
        assert_status(response, f"Error fetching OpenAPI schema from {url}.")
        return response.json()
