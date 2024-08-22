import argparse
import json
import os
import random
import string
import sys
import tempfile
import time

import requests

from sema4ai_agent_server.schema import (
    AgentReasoning,
    LLMProvider,
    OpenAIGPT,
    OpenAIGPTConfig,
)
from sema4ai_agent_server.storage import basemodel_secret_encoder_for_db


def create_agent(base_url, openai_api_key):
    """Creates a new agent."""
    model = OpenAIGPT(
        provider=LLMProvider.OPENAI,
        name="gpt-3.5-turbo",
        config=OpenAIGPTConfig(temperature=0.0, openai_api_key=openai_api_key),
    )
    url = f"{base_url}/agents"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {
        "name": "Hello",
        "description": "This is a test agent",
        "runbook": "This is a test runbook",
        "config": {
            "configurable": {
                "tools": [],
            }
        },
        "model": json.loads(model.json(encoder=basemodel_secret_encoder_for_db)),
        "architecture": "agent",
        "reasoning": AgentReasoning.DISABLED,
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["id"]
    else:
        print(f"Error creating agent: {response.status_code} {response.text}")
        sys.exit(1)


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
        sys.exit(1)


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
        print(f"Error sending message: {response.status_code} {response.text}")
        return

    current_message = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                data = json.loads(decoded_line[6:])
                if isinstance(data, list) and len(data) > 0:
                    message_part = data[0]
                    if message_part["type"] == "ai":
                        current_message = message_part["content"]
                        print(".", end="", flush=True)
                        finish_reason = message_part.get("response_metadata", {}).get(
                            "finish_reason"
                        )
                        if finish_reason == "stop":
                            print("\n  Final AI response:")
                            print(f"  {current_message}")
                            break
                    if message_part["type"] == "tool_event":
                        print(message_part)

    if not current_message:
        print("\n  No AI response received.")


def create_async_run(base_url, thread_id, message):
    """Creates an asynchronous run for the specified thread."""
    url = f"{base_url}/runs"
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


def get_file(base_url, agent_id, thread_id, file_ref):
    """Retrieves a file using the new get-file endpoint."""
    url = f"{base_url}/get-file"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {
        "agent_id": agent_id,
        "thread_id": thread_id,
        "file_ref": file_ref,
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving file: {response.status_code} {response.text}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Interact with the API")
    parser.add_argument(
        "--host", default="localhost", help="API host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8100, help="API port (default: 8100)"
    )
    parser.add_argument(
        "--openai_api_key", type=str, default="", help="OpenAI API key."
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}/api/v1"

    print("\n" + "=" * 50)
    print("STARTING API INTERACTION TEST")
    print("=" * 50)

    # Create agent
    print("\n1. CREATING AGENT")
    print("-" * 50)
    agent_id = create_agent(base_url, args.openai_api_key)
    print(f"  Created agent with ID: {agent_id}")

    # Create thread
    print("\n2. CREATING THREAD")
    print("-" * 50)
    thread_id = create_thread(base_url, agent_id)
    print(f"  Created thread with ID: {thread_id}")

    # Send a message and stream the response
    print("\n3. SENDING MESSAGE AND STREAMING RESPONSE")
    print("-" * 50)
    message = "question"
    print(f"  Sending message: {message}")
    send_message(base_url, thread_id, message)

    # Create an asynchronous run
    print("\n4. CREATING ASYNCHRONOUS RUN")
    print("-" * 50)
    async_message = "What's the weather like today?"
    print(f"  Creating async run with message: {async_message}")
    async_run_response = create_async_run(base_url, thread_id, async_message)
    print("  Async run response:")
    print(f"  {json.dumps(async_run_response, indent=2)}")

    # Wait for 5 seconds
    print("\n5. WAITING FOR RESPONSE")
    print("-" * 50)
    print("  Waiting for 5 seconds...")
    time.sleep(5)

    # Get thread state
    print("\n6. RETRIEVING THREAD STATE")
    print("-" * 50)
    thread_state = get_thread_state(base_url, thread_id)

    if thread_state and thread_state["last_ai_message"]:
        print("  Last AI message:")
        print(f"  Content: {thread_state['last_ai_message']['content']}")
        print(f"  ID: {thread_state['last_ai_message']['id']}")
    else:
        print("  No AI message found in the thread state.")
        print("\n  Full thread state:")
        print(f"  {json.dumps(thread_state['full_state'], indent=2)}")

    key_value_pairs = []

    # 7. Test file upload to thread
    print("\n7. TESTING FILE UPLOAD TO THREAD")
    print("-" * 50)
    sample_file, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    print(f"  Created sample file: {sample_file}")
    response = upload_file_to_thread(base_url, thread_id, sample_file)
    if response.status_code == 200:
        print("  Successfully uploaded file to thread")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(
            f"  Error uploading file to thread: {response.status_code} {response.text}"
        )

    # 8. Test file upload to agent
    print("\n8. TESTING FILE UPLOAD TO AGENT")
    print("-" * 50)
    sample_file2, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    response = upload_file_to_agent(base_url, agent_id, sample_file2)
    if response.status_code == 200:
        print("  Successfully uploaded file to agent")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(
            f"  Error uploading file to agent: {response.status_code} {response.text}"
        )

    # 9. Test multiple file upload to thread
    print("\n9. TESTING MULTIPLE FILE UPLOAD TO THREAD")
    print("-" * 50)
    sample_file3, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    sample_file4, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    files = [
        (
            "files",
            (os.path.basename(sample_file3), open(sample_file3, "rb"), "text/plain"),
        ),
        (
            "files",
            (os.path.basename(sample_file4), open(sample_file4, "rb"), "text/plain"),
        ),
    ]
    response = requests.post(f"{base_url}/threads/{thread_id}/files", files=files)
    if response.status_code == 200:
        print("  Successfully uploaded multiple files to thread")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(
            f"  Error uploading multiple files to thread: {response.status_code} {response.text}"
        )

    # 10. Test multiple file upload to agent
    print("\n10. TESTING MULTIPLE FILE UPLOAD TO AGENT")
    print("-" * 50)
    sample_file5, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    sample_file6, key, value = create_sample_file()
    if key and value:
        key_value_pairs.append((key, value))
    files = [
        (
            "files",
            (os.path.basename(sample_file5), open(sample_file5, "rb"), "text/plain"),
        ),
        (
            "files",
            (os.path.basename(sample_file6), open(sample_file6, "rb"), "text/plain"),
        ),
    ]
    response = requests.post(f"{base_url}/agents/{agent_id}/files", files=files)
    if response.status_code == 200:
        print("  Successfully uploaded multiple files to agent")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
        uploaded_files = response.json()
    else:
        print(
            f"  Error uploading multiple files to agent: {response.status_code} {response.text}"
        )
        uploaded_files = []

    # 11. Test get-file endpoint
    print("\n11. TESTING GET-FILE ENDPOINT")
    print("-" * 50)
    if uploaded_files:
        file_ref = uploaded_files[0]["file_ref"]
        print(f"  Retrieving file with file_ref: {file_ref}")
        file_info = get_file(base_url, agent_id, thread_id, file_ref)
        if file_info:
            print("  Successfully retrieved file information:")
            print(f"  {json.dumps(file_info, indent=2)}")
        else:
            print("  Failed to retrieve file information")
    else:
        print("  No files available to test get-file endpoint")

    # Clean up temporary files
    os.unlink(sample_file)
    os.unlink(sample_file2)
    os.unlink(sample_file3)
    os.unlink(sample_file4)
    os.unlink(sample_file5)
    os.unlink(sample_file6)

    # 12. Ask a question to retrieve a random key's value using the stream endpoint
    print("\n12. RETRIEVING A RANDOM KEY'S VALUE (USING STREAM ENDPOINT)")
    print("-" * 50)
    if key_value_pairs:
        random_key, expected_value = random.choice(key_value_pairs)
        question = f"Use the Retriever tool to look up information in uploaded files. What is the value associated with the key '{random_key}'?"
        print(f"  Asking question: {question}")
        send_message(base_url, thread_id, question)

        print(f"\n  Expected value: {expected_value}")
    else:
        print("  No key-value pairs were generated during file uploads.")

    print("\n" + "=" * 50)
    print("API INTERACTION TEST COMPLETED")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
