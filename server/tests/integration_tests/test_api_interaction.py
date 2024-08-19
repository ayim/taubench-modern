import argparse
import json
import sys
import time

import requests


def create_assistant(base_url):
    """Creates a new assistant."""
    url = f"{base_url}/assistants"
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
        return response.json()["assistant_id"]
    else:
        print(f"Error creating assistant: {response.status_code} {response.text}")
        sys.exit(1)


def create_thread(base_url, assistant_id):
    """Creates a new thread for the given assistant."""
    url = f"{base_url}/threads"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {
        "assistant_id": assistant_id,
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

    # Create assistant
    print("\n1. CREATING ASSISTANT")
    print("-" * 50)
    assistant_id = create_assistant(base_url)
    print(f"  Created assistant with ID: {assistant_id}")

    # Create thread
    print("\n2. CREATING THREAD")
    print("-" * 50)
    thread_id = create_thread(base_url, assistant_id)
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

    print("\n" + "=" * 50)
    print("API INTERACTION TEST COMPLETED")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
