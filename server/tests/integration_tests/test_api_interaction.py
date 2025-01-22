import json
import os
import random
import string
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, TypedDict

import requests
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
from colorama import Fore, Style, init
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
init(
    # Note: auto-reset is disabled as it doesn't mesh with pytest very well.
    autoreset=False
)


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


HEADER_INDEX = 0

ran_number = random.randint(1, 1000)
ran_agent_name = f"TestAgent-{ran_number}"


def print_header(message):
    global HEADER_INDEX
    HEADER_INDEX += 1
    header = f"[{timestamp()}] {HEADER_INDEX}. {message}"
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{header}{Fore.RESET}")
    print(Fore.CYAN + ("-" * len(header)) + Fore.RESET)


def print_success(message):
    print(f"{Fore.GREEN}{message}{Fore.RESET}")


def print_error(message):
    print(f"{Fore.RED}{message}{Fore.RESET}")


def print_warning(message):
    print(f"{Fore.YELLOW}{message}{Fore.RESET}")


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


def create_agent(
    base_url,
    openai_api_key,
    name: str = ran_agent_name,
    architecture=DEFAULT_ARCHITECTURE,
    action_packages: Sequence[ActionPackageDataClass] = (),
):
    """Creates a new agent."""
    from dataclasses import asdict

    model = OpenAIGPT(
        provider=LLMProvider.OPENAI,
        name="gpt-3.5-turbo",
        config=OpenAIGPTConfig(temperature=0.0, openai_api_key=openai_api_key),
    )
    metadata = AgentMetadata(mode=AgentMode.CONVERSATIONAL)
    advanced_config = AgentAdvancedConfig(
        architecture=architecture, reasoning=AgentReasoning.DISABLED
    )
    url = f"{base_url}/agents"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if name is None:
        name = f"Test Agent {timestamp()}"

    action_packages_raw: list[dict] = [asdict(ap) for ap in action_packages]
    data = {
        "public": True,
        "name": name,
        "description": "This is a test agent",
        "runbook": "This is a test runbook",
        "version": "0.0.1",
        "model": model.model_dump(mode="json", context=RAW_CONTEXT),
        "advanced_config": advanced_config.model_dump(mode="json", context=RAW_CONTEXT),
        "action_packages": action_packages_raw,
        "metadata": metadata.model_dump(mode="json", context=RAW_CONTEXT),
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["id"]
    else:
        print(f"Error creating agent: {response.status_code} {response.text}")
        return None


def delete_agent(base_url, agent_id):
    """Delete an agent by ID."""
    url = f"{base_url}/agents/{agent_id}"
    try:
        response = requests.delete(url)
        if response.status_code == 200:
            print_success(f"Successfully deleted agent with ID: {agent_id}")
        else:
            print_warning(
                f"Unexpected status code {response.status_code} when deleting agent {agent_id}"
            )
    except Exception as e:
        print_warning(f"Error occurred while deleting agent {agent_id}: {str(e)}")


def create_thread(base_url: str, agent_id: str) -> str:
    """Creates a new thread for the given agent."""
    url = f"{base_url}/threads"
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
    if response.status_code == 200:
        return response.json()["thread_id"]

    raise Exception(f"Error creating thread: {response.status_code} {response.text}")


def send_message(base_url, thread_id, message) -> str:
    """Sends a message to the specified thread and streams the response."""
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
            }
        ],
        "thread_id": thread_id,
    }

    response = requests.post(url, headers=headers, json=data, stream=True)
    assert (
        response.status_code == 200
    ), f"Error sending message: {response.status_code} {response.text}"

    current_message = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                data = json.loads(decoded_line[6:])
                if isinstance(data, list) and len(data) > 0:
                    message_part = data[-1]
                    if message_part["type"] == "ai":
                        current_message = message_part["content"]
                        print(".", end="", flush=True)
                        finish_reason = message_part.get("response_metadata", {}).get(
                            "finish_reason"
                        )
                        if finish_reason == "stop":
                            print("\nFinal AI response:")
                            print(f"{current_message}")
                            break
                    elif message_part["type"] == "tool_event":
                        tool_name = message_part.get("name", "Unknown tool")
                        tool_call_id = message_part.get("tool_call_id", "N/A")
                        input_data = message_part.get("input", {})
                        output_data = message_part.get("output")

                        if output_data is None:
                            # This is a tool call
                            print(f"\nTool Call: {tool_name}")
                            print(f"  Call ID: {tool_call_id}")
                            for key, value in input_data.items():
                                print(f"  {key}: {value}")
                        else:
                            # This is a tool return
                            print(f"\nTool Return: {tool_name}")
                            print(f"  Call ID: {tool_call_id}")
                            if isinstance(output_data, str):
                                print(
                                    f"  Output: '{output_data[:100]}...'"
                                    if len(output_data) > 100
                                    else f"  Output: '{output_data}'"
                                )
                            elif isinstance(output_data, dict):
                                for key, value in output_data.items():
                                    print(
                                        f"  {key}: '{value[:100]}...'"
                                        if isinstance(value, str) and len(value) > 100
                                        else f"  {key}: '{value}'"
                                    )
                        print("", end="", flush=True)

    if not current_message:
        print_warning("\nNo AI response received.")

    return current_message


def create_async_run(base_url: str, thread_id: str, message: str) -> dict:
    """Creates an asynchronous run for the specified thread."""
    url = f"{base_url}/runs/async_invoke"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {
        "thread_id": thread_id,
        "input": [{"content": message, "type": "human", "example": False}],
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(
            f"Error creating async run: {response.status_code} {response.text}"
        )
    result = response.json()
    assert result, f"Async run creation failed. Response: {result!r}"
    return result


def get_run_status(base_url, run_id):
    """Retrieves the status of an asynchronous run."""
    url = f"{base_url}/runs/{run_id}/status"
    headers = {
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print_error(
            f"Error retrieving run status: {response.status_code} {response.text}"
        )
        return None


class ThreadStateTypedDict(TypedDict):
    full_state: dict
    last_ai_message: dict | None


def get_thread_state(base_url: str, thread_id: str) -> ThreadStateTypedDict:
    """Retrieves the state of the specified thread and extracts the last AI message."""
    url = f"{base_url}/threads/{thread_id}/state"
    headers = {
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Error retrieving thread state: {response.status_code} {response.text}"
        )

    state = response.json()
    messages = state["values"]["messages"]
    ai_messages = [msg for msg in messages if msg["type"] == "ai"]
    last_ai_message = ai_messages[-1] if ai_messages else None
    return {"full_state": state, "last_ai_message": last_ai_message}


def create_sample_file(content=None):
    if content is None:
        key = "".join(random.choices(string.ascii_lowercase, k=5))
        value = "".join(random.choices(string.ascii_lowercase, k=5))
        content = f"This is a sample file for testing. Key: {key}, Value: {value}"
    else:
        key, value = None, None

    temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    temp_file.write(content)
    temp_file.close()
    return temp_file.name, key, value


def upload_file_to_thread(base_url, thread_id, file_path):
    url = f"{base_url}/threads/{thread_id}/files"
    with open(file_path, "rb") as file:
        files = {"files": (os.path.basename(file_path), file, "text/plain")}
        response = requests.post(url, files=files)
    return response


def upload_file_to_agent(base_url, agent_id, file_path):
    url = f"{base_url}/agents/{agent_id}/files"
    with open(file_path, "rb") as file:
        files = {"files": (os.path.basename(file_path), file, "text/plain")}
        response = requests.post(url, files=files)
    return response


def get_agent_status(base_url, agent_id) -> AgentStatus:
    url = f"{base_url}/agents/{agent_id}/status"
    response = requests.get(url)
    return AgentStatus.model_validate_json(response.text)


def get_file_by_ref(base_url, thread_id, file_ref):
    """Retrieves a file using the new get-file endpoint."""
    url = f"{base_url}/threads/{thread_id}/file-by-ref"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    params = {"file_ref": file_ref}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving file: {response.status_code} {response.text}")
        return None


def upload_multiple_files(base_url, endpoint, id, file_paths):
    url = f"{base_url}/{endpoint}/{id}/files"
    files = [
        ("files", (os.path.basename(file_path), open(file_path, "rb"), "text/plain"))
        for file_path in file_paths
    ]
    response = requests.post(url, files=files)
    return response


def create_agent_and_return_agent_id(
    base_url: str,
    openai_api_key: str,
    action_packages: Sequence[ActionPackageDataClass] = (),
) -> str:
    print_header("CREATING AGENT")
    agent_id = create_agent(base_url, openai_api_key, action_packages=action_packages)
    assert agent_id is not None, "Agent id is None right after creation"
    print_success(f"Created agent with ID: {agent_id}")
    return agent_id


def create_thread_and_return_thread_id(base_url: str, agent_id: str) -> str:
    print_header("CREATING THREAD")
    thread_id = create_thread(base_url, agent_id)
    assert thread_id is not None, "Thread id is None right after creation"
    print_success(f"Created thread with ID: {thread_id}")
    return thread_id


def send_message_to_agent_thread(
    base_url: str, thread_id: str, message: str = "question"
) -> str:
    print_header("SENDING MESSAGE AND STREAMING RESPONSE")
    print(f"Sending message: {message}")
    response = send_message(base_url, thread_id, message)
    assert response, f"Received empty response from agent: {response!r}"
    print_success("Received response from the agent")
    return response


def make_async_run(base_url: str, thread_id: str) -> None:
    print_header("TESTING ASYNCHRONOUS RUN")
    async_message = "What's the weather like today?"
    print(f"Creating async run with message: {async_message}")
    async_run_response = create_async_run(base_url, thread_id, async_message)
    assert (
        "run_id" in async_run_response
    ), f"Async run ID not received in response: {async_run_response!r}"

    run_id = async_run_response["run_id"]
    print_success(f"Async run created with ID: {run_id}")

    print("Polling for run completion")
    with tqdm(total=100, desc="Run Progress", ncols=70) as pbar:
        while True:
            status_response = get_run_status(base_url, run_id)
            if status_response and status_response["status"] == "complete":
                pbar.update(100 - pbar.n)
                # fail if pbar is full
                if pbar.n > 100:
                    raise Exception("async poll failure, pbar overflow")
                break
            if status_response is None:
                raise Exception("async poll failure (status response is None)")
            pbar.update(2)
            time.sleep(0.5)

    print_success("Run completed successfully")

    thread_state = get_thread_state(base_url, thread_id)

    if not thread_state["last_ai_message"]:
        raise AssertionError(
            "No AI message found in the thread state after async run. Received thread state: "
            f"{thread_state!r}"
        )
    print_success("Received AI message after async run")


def make_file_uploads(
    base_url: str, thread_id: str, agent_id: str
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    print_header("TESTING FILE UPLOADS")

    # Thread file upload
    thread_file, thread_key, thread_value = create_sample_file()
    thread_response = upload_file_to_thread(base_url, thread_id, thread_file)
    assert (
        thread_response.status_code == 200
    ), f"File upload to thread: bad response: {thread_response.status_code} {thread_response.text}"

    # Agent file upload
    agent_file, agent_key, agent_value = create_sample_file()
    agent_response = upload_file_to_agent(base_url, agent_id, agent_file)
    assert (
        agent_response.status_code == 200
    ), f"File upload to agent: bad response: {agent_response.status_code} {agent_response.text}"

    # Multiple file uploads
    multi_files = [create_sample_file()[0] for _ in range(4)]
    agent_files, thread_files = multi_files[:2], multi_files[2:]
    thread_multi_response = upload_multiple_files(
        base_url, "threads", thread_id, agent_files
    )
    assert (
        thread_multi_response.status_code == 200
    ), f"Multiple file upload to thread: bad response: {thread_multi_response.status_code} {thread_multi_response.text}"

    agent_multi_response = upload_multiple_files(
        base_url, "agents", agent_id, thread_files
    )

    assert (
        agent_multi_response.status_code == 200
    ), f"Multiple file upload to agent: bad response: {agent_multi_response.status_code} {agent_multi_response.text}"

    total_files = 1 + 1 + 2 + 2  # 1 thread, 1 agent, 2 multi-thread, 2 multi-agent
    print_success(f"Successfully uploaded {total_files} files")

    return (
        [agent_file] + agent_files,
        [thread_file] + thread_files,
        [
            (thread_key, thread_value),
            (agent_key, agent_value),
        ],
    )


def check_get_file(base_url, thread_id, uploaded_thread_files):
    print_header("TESTING FILE RETRIEVAL")
    if not uploaded_thread_files:
        raise Exception("No files available to test file retrieval")

    file_ref = os.path.basename(uploaded_thread_files[0])
    file_info = get_file_by_ref(base_url, thread_id, file_ref)
    assert file_info is not None, "File information retrieval"
    assert (
        file_ref in file_info["file_url"]
    ), "Retrieved file_ref matches the requested one"
    print_success(f"Successfully retrieved file information for {file_ref}")


def check_retrieval(
    base_url: str, thread_id: str, key_value_pairs: list[tuple[str, str]]
):
    print_header("TESTING INFORMATION RETRIEVAL")
    if not key_value_pairs:
        raise AssertionError("No key-value pairs available for testing retrieval")

    random_key, expected_value = random.choice(key_value_pairs)
    question = f"What is the value associated with the key '{random_key}'?"
    print(f"Asking question: {question}")
    response = send_message(base_url, thread_id, question)
    assert (
        expected_value in response
    ), f"Expected value '{expected_value}' found in the response"
    print_success(f"Successfully retrieved value for key '{random_key}'")


def wait_for_agent_readiness(base_url, agent_id, timeout=20):
    print_header("WAITING FOR AGENT READINESS")
    start_time = time.time()

    while True:
        status = get_agent_status(base_url, agent_id)
        if status.ready:
            print_success("Agent is ready")
            return

        if time.time() - start_time > timeout:
            issues = status.issues
            raise TimeoutError(
                f"Agent {agent_id} did not become ready within {timeout} seconds. {issues}"
            )

        time.sleep(0.5)


def get_openapi_schema(base_url: str) -> dict:
    url = f"{base_url}/openapi.json"
    print(f"Fetching OpenAPI schema from {url}")
    response = requests.get(url)
    return response.json()


def test_api_interaction_with_action_server(
    base_url_agent_server,
    openai_api_key,
    tmpdir,
    datadir,
    action_server_process,
    logs_dir,
):
    start_time = time.time()
    cwd = datadir / "simple_action_package"
    api_key = "test"
    action_server_process.start(
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,  # Can be slow (time to bootstrap env)
        additional_args=["--api-key", api_key],
        logs_dir=logs_dir,
    )
    url = f"http://{action_server_process.host}:{action_server_process.port}"
    base_url_api = f"{base_url_agent_server}/api/v1"

    agent_id = create_agent_and_return_agent_id(
        base_url_api,
        openai_api_key,
        action_packages=[
            ActionPackageDataClass(
                name="ActionPackage",
                organization="Organization",
                version="0.0.1",
                url=url,
                api_key=api_key,
                whitelist="",
            )
        ],
    )
    wait_for_agent_readiness(base_url_api, agent_id, timeout=60)

    try:
        thread_id = create_thread_and_return_thread_id(base_url_api, agent_id)
        result = send_message_to_agent_thread(
            base_url_api, thread_id, "Which actions are available to you?"
        ).lower()
        if "list contact" not in result and "listing all contacts" not in result:
            raise AssertionError(
                "Agent did not provide that it has the list contact action. Found result: "
                f"{result!r}"
            )
        result = send_message_to_agent_thread(
            base_url_api, thread_id, "Please list all contacts"
        ).lower()
        if "john doe" not in result and "jane doe" not in result:
            raise AssertionError(
                "Agent did not find contacts: 'john doe' or 'jane doe'. Found result: "
                f"{result!r}"
            )

    finally:
        delete_agent(base_url_api, agent_id)

    end_time = time.time()
    duration = end_time - start_time
    print(f"\nTotal test duration: {duration:.2f} seconds")


def test_api_interaction(base_url_agent_server, openai_api_key):
    start_time = time.time()

    base_url_api = f"{base_url_agent_server}/api/v1"

    agent_id = create_agent_and_return_agent_id(base_url_api, openai_api_key)
    wait_for_agent_readiness(base_url_api, agent_id)
    uploaded_agent_files = []
    uploaded_thread_files = []

    try:
        thread_id = create_thread_and_return_thread_id(base_url_api, agent_id)
        send_message_to_agent_thread(base_url_api, thread_id)
        make_async_run(base_url_api, thread_id)
        uploaded_agent_files, uploaded_thread_files, key_value_pairs = (
            make_file_uploads(base_url_api, thread_id, agent_id)
        )
        check_get_file(base_url_api, thread_id, uploaded_thread_files)
        check_retrieval(base_url_api, thread_id, key_value_pairs)

        print_header("TEARDOWN")
    finally:
        delete_agent(base_url_api, agent_id)

        # Clean up files
        for file_path in uploaded_agent_files + uploaded_thread_files:
            os.unlink(file_path)

    end_time = time.time()
    duration = end_time - start_time
    print(f"\nTotal test duration: {duration:.2f} seconds")


if __name__ == "__main__":
    import pytest

    # Can be set to start the agent server in the test
    os.environ["INTEGRATION_TEST_START_SERVER"] = "true"
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
