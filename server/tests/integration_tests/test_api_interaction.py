import argparse
import json
import os
import random
import string
import sys
import tempfile
import time
from datetime import datetime

import requests
from colorama import Fore, Style, init
from dotenv import load_dotenv
from pydantic import parse_obj_as
from tqdm import tqdm

from sema4ai_agent_server.schema import (
    AgentArchitecture,
    AgentMetadata,
    AgentMode,
    AgentReasoning,
    AgentStatus,
    LLMProvider,
    OpenAIGPT,
    OpenAIGPTConfig,
)
from sema4ai_agent_server.storage import basemodel_secret_encoder_for_db

load_dotenv()
init(autoreset=True)  # Initialize colorama

test_results = []


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


HEADER_INDEX = 0


def print_header(message):
    global HEADER_INDEX
    HEADER_INDEX += 1
    header = f"[{timestamp()}] {HEADER_INDEX}. {message}"
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{header}")
    print(Fore.CYAN + ("-" * len(header)))


def print_success(message):
    print(f"{Fore.GREEN}{message}")


def print_error(message):
    print(f"{Fore.RED}{message}")


def print_warning(message):
    print(f"{Fore.YELLOW}{message}")


def assert_test(condition, message):
    global test_results
    if not condition:
        print_error(f"ASSERTION FAILED: {message}")
        test_results.append((False, message))
    else:
        test_results.append((True, message))


def create_agent(
    base_url,
    openai_api_key,
    name: str = "Agent",
    architecture=AgentArchitecture.AGENT,
):
    """Creates a new agent."""
    model = OpenAIGPT(
        provider=LLMProvider.OPENAI,
        name="gpt-3.5-turbo",
        config=OpenAIGPTConfig(temperature=0.0, openai_api_key=openai_api_key),
    )
    metadata = AgentMetadata(mode=AgentMode.CONVERSATIONAL)
    url = f"{base_url}/agents"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    data = {
        "public": True,
        "name": name,
        "description": "This is a test agent",
        "runbook": "This is a test runbook",
        "version": "0.0.1",
        "model": json.loads(model.json(encoder=basemodel_secret_encoder_for_db)),
        "architecture": architecture,
        "reasoning": AgentReasoning.DISABLED,
        "action_packages": [],
        "metadata": json.loads(metadata.json(encoder=basemodel_secret_encoder_for_db)),
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


def create_thread(base_url, agent_id):
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
    else:
        print(f"Error creating thread: {response.status_code} {response.text}")
        return None


def send_message(base_url, thread_id, message):
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
    if response.status_code != 200:
        print_error(f"Error sending message: {response.status_code} {response.text}")
        return None

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


def create_async_run(base_url, thread_id, message):
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
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error creating async run: {response.status_code} {response.text}")
        return None


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


def get_thread_state(base_url, thread_id):
    """Retrieves the state of the specified thread and extracts the last AI message."""
    url = f"{base_url}/threads/{thread_id}/state"
    headers = {
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        state = response.json()
        messages = state["values"]["messages"]
        ai_messages = [msg for msg in messages if msg["type"] == "ai"]
        last_ai_message = ai_messages[-1] if ai_messages else None
        return {"full_state": state, "last_ai_message": last_ai_message}
    else:
        print(f"Error retrieving thread state: {response.status_code} {response.text}")
        return None


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
    return parse_obj_as(AgentStatus, response.json())


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


def test_agent_creation(base_url, openai_api_key):
    print_header("CREATING AGENT")
    agent_id = create_agent(base_url, openai_api_key)
    assert_test(agent_id is not None, "Agent creation")
    if agent_id:
        print_success(f"Created agent with ID: {agent_id}")
    return agent_id


def test_vitality_agent_creation(base_url, openai_api_key):
    print_header("CREATING VITALITY AGENT")
    agent_id = create_agent(
        base_url,
        openai_api_key,
        name="Vital",
        architecture=AgentArchitecture.MULTI_AGENT_HIERARCHICAL_PLANNING,
    )
    assert_test(agent_id is not None, "Agent creation")
    if agent_id:
        print_success(f"Created agent with ID: {agent_id}")
    return agent_id


def test_thread_creation(base_url, agent_id):
    print_header("CREATING THREAD")
    thread_id = create_thread(base_url, agent_id)
    assert_test(thread_id is not None, "Thread creation")
    if thread_id:
        print_success(f"Created thread with ID: {thread_id}")
    return thread_id


def test_message_sending(base_url, thread_id):
    print_header("SENDING MESSAGE AND STREAMING RESPONSE")
    message = "question"
    print(f"Sending message: {message}")
    response = send_message(base_url, thread_id, message)
    assert_test(response is not None, "Message sending and response")
    if response:
        print_success("Received response from the agent")


def test_async_run(base_url, thread_id):
    print_header("TESTING ASYNCHRONOUS RUN")
    async_message = "What's the weather like today?"
    print(f"Creating async run with message: {async_message}")
    async_run_response = create_async_run(base_url, thread_id, async_message)
    assert_test(async_run_response is not None, "Async run creation")
    assert_test("run_id" in async_run_response, "Async run ID received")

    if async_run_response and "run_id" in async_run_response:
        run_id = async_run_response["run_id"]
        print_success(f"Async run created with ID: {run_id}")

        print("Polling for run completion")
        with tqdm(total=100, desc="Run Progress", ncols=70) as pbar:
            while True:
                status_response = get_run_status(base_url, run_id)
                if status_response and status_response["status"] == "complete":
                    pbar.update(100 - pbar.n)
                    break
                if status_response is None:
                    assert_test(status_response, "async poll failure")
                    return
                pbar.update(2)
                time.sleep(0.5)

        print_success("Run completed successfully")

        thread_state = get_thread_state(base_url, thread_id)
        assert_test(thread_state is not None, "Thread state retrieval after async run")
        assert_test(
            "last_ai_message" in thread_state,
            "AI message in thread state after async run",
        )

        if thread_state and thread_state["last_ai_message"]:
            print_success("Received AI message after async run")
        else:
            print_warning("No AI message found in the thread state after async run")


def test_file_uploads(base_url, thread_id, agent_id):
    print_header("TESTING FILE UPLOADS")

    # Thread file upload
    thread_file, thread_key, thread_value = create_sample_file()
    thread_response = upload_file_to_thread(base_url, thread_id, thread_file)
    assert_test(thread_response.status_code == 200, "File upload to thread")

    # Agent file upload
    agent_file, agent_key, agent_value = create_sample_file()
    agent_response = upload_file_to_agent(base_url, agent_id, agent_file)
    assert_test(agent_response.status_code == 200, "File upload to agent")

    # Multiple file uploads
    multi_files = [create_sample_file()[0] for _ in range(4)]
    agent_files, thread_files = multi_files[:2], multi_files[2:]
    thread_multi_response = upload_multiple_files(
        base_url, "threads", thread_id, agent_files
    )
    agent_multi_response = upload_multiple_files(
        base_url, "agents", agent_id, thread_files
    )

    assert_test(
        thread_multi_response.status_code == 200, "Multiple file upload to thread"
    )
    assert_test(
        agent_multi_response.status_code == 200, "Multiple file upload to agent"
    )

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


def test_get_file(base_url, thread_id, uploaded_thread_files):
    print_header("TESTING FILE RETRIEVAL")
    if uploaded_thread_files:
        file_ref = os.path.basename(uploaded_thread_files[0])
        file_info = get_file_by_ref(base_url, thread_id, file_ref)
        assert_test(file_info is not None, "File information retrieval")
        assert_test(
            file_ref in file_info["file_url"],
            "Retrieved file_ref matches the requested one",
        )
        if file_info:
            print_success(f"Successfully retrieved file information for {file_ref}")
    else:
        print_warning("No files available to test file retrieval")


def test_retrieval(base_url, thread_id, key_value_pairs):
    print_header("TESTING INFORMATION RETRIEVAL")
    if key_value_pairs:
        random_key, expected_value = random.choice(key_value_pairs)
        question = f"What is the value associated with the key '{random_key}'?"
        print(f"Asking question: {question}")
        response = send_message(base_url, thread_id, question)
        assert_test(response is not None, "Retrieval response received")
        assert_test(
            expected_value in response,
            f"Expected value '{expected_value}' found in the response",
        )
        if expected_value in response:
            print_success(f"Successfully retrieved value for key '{random_key}'")
    else:
        print_warning("No key-value pairs available for testing retrieval")


def wait_for_agent_readiness(base_url, agent_id):
    print_header("WAITING FOR AGENT READINESS")
    start_time = time.time()
    timeout = 20  # 20 seconds timeout

    while True:
        status = get_agent_status(base_url, agent_id)
        if status.ready:
            print_success("Agent is ready")
            return

        if time.time() - start_time > timeout:
            raise TimeoutError(
                f"Agent {agent_id} did not become ready within {timeout} seconds"
            )

        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="Interact with the API")
    parser.add_argument(
        "--host", default="localhost", help="API host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8100, help="API port (default: 8100)"
    )
    parser.add_argument(
        "--openai_api_key", type=str, default=None, help="OpenAI API key."
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}/api/v1"

    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}STARTING API INTERACTION TEST")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")

    start_time = time.time()

    openai_api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        sys.exit(1)

    agent_id = test_agent_creation(base_url, openai_api_key)
    wait_for_agent_readiness(base_url, agent_id)
    thread_id = test_thread_creation(base_url, agent_id)
    test_message_sending(base_url, thread_id)
    test_async_run(base_url, thread_id)
    uploaded_agent_files, uploaded_thread_files, key_value_pairs = test_file_uploads(
        base_url, thread_id, agent_id
    )
    test_get_file(base_url, thread_id, uploaded_thread_files)
    test_retrieval(base_url, thread_id, key_value_pairs)

    vitality_agent_id = test_vitality_agent_creation(base_url, openai_api_key)

    print_header("TEARDOWN")

    delete_agent(base_url, agent_id)
    delete_agent(base_url, vitality_agent_id)

    # Clean up files
    for file_path in uploaded_agent_files + uploaded_thread_files:
        os.unlink(file_path)

    # Summarize test results
    total_tests = len(test_results)
    passed_tests = sum(result[0] for result in test_results)

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.CYAN}{Style.BRIGHT}TEST SUMMARY")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
    print(f"{Fore.GREEN}Passed: {passed_tests}/{total_tests}")

    if passed_tests < total_tests:
        print(f"\n{Fore.RED}Failed Tests:")
        for passed, message in test_results:
            if not passed:
                print(f"{Fore.RED}- {message}")

    end_time = time.time()
    duration = end_time - start_time
    print(f"\n{Fore.YELLOW}Total test duration: {duration:.2f} seconds")

    # Exit with non-zero status if any test failed
    if passed_tests < total_tests:
        sys.exit(1)


if __name__ == "__main__":
    main()
