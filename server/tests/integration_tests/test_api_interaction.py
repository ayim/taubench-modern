import argparse
import json
import os
import sys
import tempfile
import time

import requests


def create_agent(base_url):
    """Creates a new agent."""
    url = f"{base_url}/agents"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {
        "name": "Hello",
        "config": {
            "configurable": {
                "type": "agent",
                "agent_type": "GPT 4o",
                "interrupt_before_action": False,
                "retrieval_description": "Can be used to look up information that was uploaded to this assistant.\nIf the user is referencing particular files, that is often a good hint that information may be here.\nIf the user asks a vague question, they are likely meaning to look up info from this retriever, and you should call it!",
                "system_message": "You are an assistant with the following name: Hello.\nThe current date and time is: ${CURRENT_DATETIME}.\nYour instructions are:\nrunbook",
                "description": "description",
                "tools": [],
                "reasoning_level": 0,
            }
        },
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
                        if "finish_reason" in message_part.get("response_metadata", {}):
                            print("\n  Final AI response:")
                            print(f"  {current_message}")
                            break

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


def create_sample_file(content="This is a sample file for testing."):
    temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def upload_file_to_thread(base_url, thread_id, file_path):
    url = f"{base_url}/threads/{thread_id}/files"
    with open(file_path, "rb") as file:
        files = {"files": (os.path.basename(file_path), file)}
        response = requests.post(url, files=files)
    return response


def upload_file_to_agent(base_url, agent_id, file_path):
    url = f"{base_url}/agents/{agent_id}/files"
    with open(file_path, "rb") as file:
        files = {"files": (os.path.basename(file_path), file)}
        response = requests.post(url, files=files)
    return response


def main():
    parser = argparse.ArgumentParser(description="Interact with the API")
    parser.add_argument(
        "--host", default="localhost", help="API host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8100, help="API port (default: 8100)"
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    print("\n" + "=" * 50)
    print("STARTING API INTERACTION TEST")
    print("=" * 50)

    # Create agent
    print("\n1. CREATING AGENT")
    print("-" * 50)
    agent_id = create_agent(base_url)
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

    # 7. Test file upload to thread
    print("\n7. TESTING FILE UPLOAD TO THREAD")
    print("-" * 50)
    sample_file = create_sample_file()
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
    sample_file2 = create_sample_file()
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
    sample_file3 = create_sample_file("This is another sample file for testing.")
    sample_file4 = create_sample_file("This is another sample file for testing.")
    files = [
        ("files", (os.path.basename(sample_file3), open(sample_file3, "rb"))),
        ("files", (os.path.basename(sample_file4), open(sample_file4, "rb"))),
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
    sample_file5 = create_sample_file("This is another sample file for testing.")
    sample_file6 = create_sample_file("This is another sample file for testing.")
    files = [
        ("files", (os.path.basename(sample_file5), open(sample_file5, "rb"))),
        ("files", (os.path.basename(sample_file6), open(sample_file6, "rb"))),
    ]
    response = requests.post(f"{base_url}/agents/{agent_id}/files", files=files)
    if response.status_code == 200:
        print("  Successfully uploaded multiple files to agent")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(
            f"  Error uploading multiple files to agent: {response.status_code} {response.text}"
        )

    # Clean up temporary files
    os.unlink(sample_file)
    os.unlink(sample_file2)

    print("\n" + "=" * 50)
    print("API INTERACTION TEST COMPLETED")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
