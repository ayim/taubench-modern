import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.thought import ThreadThoughtContent
from agent_platform.core.user import User
from agent_platform.server.api.private_v2.threads import router as threads_router
from agent_platform.server.auth.handlers import auth_user


# Create a mock storage class
class MockStorage:
    """Mock storage class for testing threads API endpoints."""

    def __init__(self):
        self.threads: dict[str, Thread] = {}
        self.users: dict[str, User] = {}
        self.call_count: dict[str, int] = {
            "get_thread": 0,
            "list_threads": 0,
            "upsert_thread": 0,
            "delete_thread": 0,
            "add_message_to_thread": 0,
            "get_agent": 0,
            "delete_threads_for_agent": 0,
            "get_or_create_user": 0,
        }

    async def get_thread(self, user_id: str, thread_id: str) -> Thread | None:
        self.call_count["get_thread"] += 1
        thread = self.threads.get(thread_id)
        if thread:
            # Simulate real storage behavior: set commited and complete to True
            # for messages retrieved from storage
            for message in thread.messages:
                message.commited = True
                message.complete = True
                # Also mark content as complete
                for content in message.content:
                    content.complete = True
        return thread

    async def list_threads(self, user_id: str) -> list[Thread]:
        self.call_count["list_threads"] += 1
        return list(self.threads.values())

    async def list_threads_for_agent(self, user_id: str, agent_id: str) -> list[Thread]:
        return [t for t in self.threads.values() if t.agent_id == agent_id]

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        self.call_count["upsert_thread"] += 1
        self.threads[thread.thread_id] = thread

    async def delete_thread(self, user_id: str, thread_id: str) -> None:
        self.call_count["delete_thread"] += 1
        if thread_id in self.threads:
            del self.threads[thread_id]

    async def add_message_to_thread(
        self, user_id: str, thread_id: str, message: ThreadMessage
    ) -> None:
        self.call_count["add_message_to_thread"] += 1
        if thread_id in self.threads:
            self.threads[thread_id].messages.append(message)

    async def get_agent(self, user_id: str, agent_id: str) -> dict[str, str]:
        self.call_count["get_agent"] += 1
        return {"agent_id": agent_id}

    async def delete_threads_for_agent(
        self, user_id: str, agent_id: str, thread_ids: list[str] | None = None
    ) -> None:
        self.call_count["delete_threads_for_agent"] += 1
        if thread_ids:
            # Delete specific threads for agent
            self.threads = {
                tid: thread
                for tid, thread in self.threads.items()
                if tid not in thread_ids or thread.agent_id != agent_id
            }
        else:
            # Delete all threads for agent
            self.threads = {
                tid: thread for tid, thread in self.threads.items() if thread.agent_id != agent_id
            }

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Get an existing user or create a new one."""
        self.call_count["get_or_create_user"] += 1
        if sub in self.users:
            return self.users[sub], False

        user = User(user_id=f"user_{len(self.users)}", sub=sub)
        self.users[sub] = user
        return user, True


@pytest.fixture
def mock_storage() -> MockStorage:
    """Create mock storage."""
    return MockStorage()


@pytest.fixture
def test_user() -> User:
    """Create a mock user for testing."""
    return User(user_id="test_user", sub="static-default-user-id")


@pytest.fixture
def test_app(mock_storage: MockStorage, test_user: User) -> FastAPI:
    """Create FastAPI test app with router and mocked dependencies."""
    app = FastAPI()
    app.include_router(threads_router, prefix="/threads")

    # Set up storage dependency
    from agent_platform.server.storage.option import StorageService

    # Override the dependencies
    app.dependency_overrides[StorageService.get_instance] = lambda: mock_storage
    app.dependency_overrides[auth_user] = lambda: test_user

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app)


def test_create_thread(client: TestClient, mock_storage: MockStorage):
    """Test creating a thread."""
    agent_id = str(uuid.uuid4())

    # Create a thread
    response = client.post(
        "/threads/",
        json={"name": "Test Thread", "agent_id": agent_id},
    )

    assert response.status_code == status.HTTP_200_OK
    thread = response.json()
    assert thread["name"] == "Test Thread"
    assert thread["agent_id"] == agent_id

    # Verify that upsert_thread was called
    assert mock_storage.call_count["upsert_thread"] == 1


def test_list_threads(client: TestClient, mock_storage: MockStorage):
    """Test listing threads without messages."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a test thread with a message
    message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Hello")],
    )
    thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[message],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = thread

    # List threads
    response = client.get("/threads/")

    assert response.status_code == status.HTTP_200_OK
    threads = response.json()
    assert len(threads) == 1
    assert threads[0]["thread_id"] == thread_id
    assert threads[0]["name"] == "Test Thread"
    assert threads[0]["agent_id"] == agent_id
    # Verify that messages are not included in the response
    assert "messages" in threads[0]
    assert threads[0]["messages"] == []

    # Verify that list_threads was called
    assert mock_storage.call_count["list_threads"] == 1


def test_get_thread(client: TestClient, mock_storage: MockStorage):
    """Test getting a thread without messages."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a test thread with a message
    message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Hello")],
    )
    thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[message],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = thread

    # Get thread
    response = client.get(f"/threads/{thread_id}")

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["thread_id"] == thread_id
    assert thread_data["name"] == "Test Thread"
    assert thread_data["agent_id"] == agent_id
    # Verify that messages are not included in the response
    assert "messages" in thread_data
    assert thread_data["messages"] == []

    # Verify that get_thread was called
    assert mock_storage.call_count["get_thread"] == 1


def test_get_thread_state(client: TestClient, mock_storage: MockStorage):
    """Test getting a thread with its messages."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a test thread with a message
    message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Hello")],
    )
    thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[message],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = thread

    # Get thread state
    response = client.get(f"/threads/{thread_id}/state")

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["thread_id"] == thread_id
    assert thread_data["name"] == "Test Thread"
    assert thread_data["agent_id"] == agent_id
    # Verify that messages are included in the response
    assert "messages" in thread_data
    assert len(thread_data["messages"]) == 1
    assert thread_data["messages"][0]["role"] == "user"
    assert thread_data["messages"][0]["content"][0]["text"] == "Hello"

    # Verify that get_thread was called
    assert mock_storage.call_count["get_thread"] == 1


def test_get_thread_state_message_flags(client: TestClient, mock_storage: MockStorage):
    """Test that thread messages have correct commited and complete flags."""
    thread_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a thread with messages
    thread = Thread(
        thread_id=thread_id,
        user_id=user_id,
        agent_id=agent_id,
        name="Test Thread",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello")],
                commited=False,  # These will be set to True by storage
                complete=False,
            ),
            ThreadMessage(
                role="agent",
                content=[
                    ThreadThoughtContent(thought="Thinking..."),
                    ThreadTextContent(text="Hi there!"),
                ],
                commited=False,
                complete=False,
            ),
        ],
    )
    mock_storage.threads[thread_id] = thread

    # Get thread state
    response = client.get(f"/threads/{thread_id}/state")
    assert response.status_code == 200

    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 2

    # Check that all messages have commited=True and complete=True
    for message in data["messages"]:
        assert message["commited"] is True, "Messages from API should have commited=True"
        assert message["complete"] is True, "Messages from API should have complete=True"

        # Check that content items also have complete=True
        for content in message["content"]:
            assert content["complete"] is True, "Content items should have complete=True"

    # Verify the message content is preserved
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"][0]["text"] == "Hello"

    assert data["messages"][1]["role"] == "agent"
    assert data["messages"][1]["content"][0]["thought"] == "Thinking..."
    assert data["messages"][1]["content"][1]["text"] == "Hi there!"


def test_get_thread_not_found(client: TestClient, mock_storage: MockStorage):
    """Test getting a thread that doesn't exist."""
    thread_id = str(uuid.uuid4())

    # Get non-existent thread
    response = client.get(f"/threads/{thread_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Verify that get_thread was called
    assert mock_storage.call_count["get_thread"] == 1


def test_update_thread(client: TestClient, mock_storage: MockStorage):
    """Test updating a thread."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create an existing thread
    existing_thread = Thread(
        thread_id=thread_id,
        name="Original Thread Name",
        agent_id=agent_id,
        user_id="test_user",
        messages=[],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = existing_thread

    # Update thread
    response = client.put(
        f"/threads/{thread_id}",
        json={"name": "Updated Thread Name", "agent_id": agent_id},
    )

    # Verify the response
    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["thread_id"] == thread_id
    assert thread_data["name"] == "Updated Thread Name"
    assert thread_data["agent_id"] == agent_id

    # Verify that the thread was updated in storage
    updated_thread = mock_storage.threads[thread_id]
    assert updated_thread.name == "Updated Thread Name"

    # Verify that get_thread and upsert_thread were called
    assert mock_storage.call_count["get_thread"] >= 1
    assert mock_storage.call_count["upsert_thread"] == 1


def test_update_thread_not_found(client: TestClient, mock_storage: MockStorage):
    """Test updating a thread that doesn't exist."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Update non-existent thread
    response = client.put(
        f"/threads/{thread_id}",
        json={"name": "Updated Thread Name", "agent_id": agent_id},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Verify that get_thread was called but upsert_thread was not
    assert mock_storage.call_count["get_thread"] == 1
    assert mock_storage.call_count["upsert_thread"] == 0


def test_delete_thread(client: TestClient, mock_storage: MockStorage):
    """Test deleting a thread."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a thread
    thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = thread

    # Delete thread
    response = client.delete(f"/threads/{thread_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify that the thread was deleted from storage
    assert thread_id not in mock_storage.threads

    # Verify that delete_thread was called
    assert mock_storage.call_count["delete_thread"] == 1


def test_add_message_to_thread(client: TestClient, mock_storage: MockStorage):
    """Test adding a message to a thread."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create a thread with a message
    message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Hello")],
    )
    thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[message],
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = thread

    # Add message to thread with proper payload format
    # The AddThreadMessagePayload requires only role and content fields
    response = client.post(
        f"/threads/{thread_id}/messages",
        json={
            "role": "agent",
            "content": [{"kind": "text", "text": "How can I help you?"}],
            "commited": True,  # Set required fields
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
    )

    # Print any errors for debugging
    if response.status_code != status.HTTP_200_OK:
        print(f"Error response: {response.status_code}")
        print(f"Response content: {response.content.decode()}")

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["thread_id"] == thread_id

    # Verify that add_message_to_thread was called
    assert mock_storage.call_count["add_message_to_thread"] == 1


def test_list_threads_with_case_insensitive_name_filter(
    client: TestClient, mock_storage: MockStorage
):
    """Test listing threads with case-insensitive name filtering."""
    agent_id = str(uuid.uuid4())

    # Create test threads with different case variations
    threads = [
        Thread(
            thread_id=str(uuid.uuid4()),
            name="Test Thread",
            agent_id=agent_id,
            user_id="test_user",
            messages=[],
        ),
        Thread(
            thread_id=str(uuid.uuid4()),
            name="ANOTHER TEST",
            agent_id=agent_id,
            user_id="test_user",
            messages=[],
        ),
        Thread(
            thread_id=str(uuid.uuid4()),
            name="production thread",
            agent_id=agent_id,
            user_id="test_user",
            messages=[],
        ),
        Thread(
            thread_id=str(uuid.uuid4()),
            name="Development Setup",
            agent_id=agent_id,
            user_id="test_user",
            messages=[],
        ),
    ]

    # Add threads to storage
    for thread in threads:
        mock_storage.threads[thread.thread_id] = thread

    # Test case-insensitive filtering with lowercase search term
    response = client.get("/threads/?name=test")
    assert response.status_code == status.HTTP_200_OK
    filtered_threads = response.json()

    # Should match "Test Thread" and "ANOTHER TEST"
    assert len(filtered_threads) == 2
    thread_names = [t["name"] for t in filtered_threads]
    assert "Test Thread" in thread_names
    assert "ANOTHER TEST" in thread_names

    # Test case-insensitive filtering with uppercase search term
    response = client.get("/threads/?name=THREAD")
    assert response.status_code == status.HTTP_200_OK
    filtered_threads = response.json()

    # Should match "Test Thread" and "production thread"
    assert len(filtered_threads) == 2
    thread_names = [t["name"] for t in filtered_threads]
    assert "Test Thread" in thread_names
    assert "production thread" in thread_names

    # Test case-insensitive filtering with mixed case search term
    response = client.get("/threads/?name=Dev")
    assert response.status_code == status.HTTP_200_OK
    filtered_threads = response.json()

    # Should match "Development Setup"
    assert len(filtered_threads) == 1
    assert filtered_threads[0]["name"] == "Development Setup"

    # Test no matches
    response = client.get("/threads/?name=nonexistent")
    assert response.status_code == status.HTTP_200_OK
    filtered_threads = response.json()
    assert len(filtered_threads) == 0


def test_patch_thread_name_only(client: TestClient, mock_storage: MockStorage):
    """Test patching only the thread name."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create an existing thread with messages
    message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Hello")],
    )
    existing_thread = Thread(
        thread_id=thread_id,
        name="Original Name",
        agent_id=agent_id,
        user_id="test_user",
        messages=[message],
        metadata={"key": "value"},
    )

    # Add thread to storage
    mock_storage.threads[thread_id] = existing_thread

    # Patch only the name
    response = client.patch(
        f"/threads/{thread_id}",
        json={"name": "Updated Name"},
    )

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["thread_id"] == thread_id
    assert thread_data["name"] == "Updated Name"
    # Verify other fields are preserved
    assert thread_data["agent_id"] == agent_id
    assert len(thread_data["messages"]) == 1
    assert thread_data["metadata"]["key"] == "value"

    # Verify storage was updated
    updated_thread = mock_storage.threads[thread_id]
    assert updated_thread.name == "Updated Name"
    assert updated_thread.agent_id == agent_id  # Unchanged
    assert len(updated_thread.messages) == 1  # Unchanged


def test_patch_thread_agent_id_only(client: TestClient, mock_storage: MockStorage):
    """Test patching only the agent_id."""
    thread_id = str(uuid.uuid4())
    original_agent_id = str(uuid.uuid4())
    new_agent_id = str(uuid.uuid4())

    existing_thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=original_agent_id,
        user_id="test_user",
        messages=[],
    )

    mock_storage.threads[thread_id] = existing_thread

    # Patch only the agent_id
    response = client.patch(
        f"/threads/{thread_id}",
        json={"agent_id": new_agent_id},
    )

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["agent_id"] == new_agent_id
    assert thread_data["name"] == "Test Thread"  # Unchanged


def test_patch_thread_multiple_fields(client: TestClient, mock_storage: MockStorage):
    """Test patching multiple fields at once."""
    thread_id = str(uuid.uuid4())
    original_agent_id = str(uuid.uuid4())
    new_agent_id = str(uuid.uuid4())

    existing_thread = Thread(
        thread_id=thread_id,
        name="Original Name",
        agent_id=original_agent_id,
        user_id="test_user",
        messages=[],
        metadata={"old": "data"},
    )

    mock_storage.threads[thread_id] = existing_thread

    # Patch multiple fields
    response = client.patch(
        f"/threads/{thread_id}",
        json={
            "name": "New Name",
            "agent_id": new_agent_id,
            "metadata": {"new": "data", "extra": "field"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["name"] == "New Name"
    assert thread_data["agent_id"] == new_agent_id
    assert thread_data["metadata"]["new"] == "data"
    assert thread_data["metadata"]["extra"] == "field"


def test_patch_thread_messages_replacement(client: TestClient, mock_storage: MockStorage):
    """Test patching messages (full replacement)."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Create thread with existing messages
    original_message = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="Original message")],
    )
    existing_thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=[original_message],
    )

    mock_storage.threads[thread_id] = existing_thread

    # Create new messages for replacement
    new_message1 = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="user",
        content=[ThreadTextContent(text="New message 1")],
    )
    new_message2 = ThreadMessage(
        message_id=str(uuid.uuid4()),
        role="agent",
        content=[ThreadTextContent(text="New message 2")],
    )

    # Patch with new messages
    with patch("agent_platform.core.context.AgentServerContext.from_request") as mock_context:
        mock_server_context = Mock()
        mock_context.return_value = mock_server_context

        response = client.patch(
            f"/threads/{thread_id}",
            json={
                "messages": [
                    {
                        "message_id": new_message1.message_id,
                        "role": "user",
                        "content": [{"kind": "text", "text": "New message 1"}],
                        "commited": True,
                        "complete": True,
                        "agent_metadata": {},
                        "server_metadata": {},
                    },
                    {
                        "message_id": new_message2.message_id,
                        "role": "agent",
                        "content": [{"kind": "text", "text": "New message 2"}],
                        "commited": True,
                        "complete": True,
                        "agent_metadata": {},
                        "server_metadata": {},
                    },
                ]
            },
        )

        assert response.status_code == status.HTTP_200_OK
        thread_data = response.json()
        assert len(thread_data["messages"]) == 2

        # Verify OTEL counter was called for messages
        mock_server_context.increment_counter.assert_called_with(
            "sema4ai.agent_server.messages",
            2,  # Should count all new messages
            {"agent_id": agent_id, "thread_id": thread_id},
        )


def test_patch_thread_not_found(client: TestClient, mock_storage: MockStorage):
    """Test patching a thread that doesn't exist."""
    thread_id = str(uuid.uuid4())

    response = client.patch(
        f"/threads/{thread_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch("agent_platform.core.context.AgentServerContext.from_request")
def test_put_thread_message_counting(mock_context, client: TestClient, mock_storage: MockStorage):
    """Test that PUT endpoint only counts new messages, not existing ones."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    mock_server_context = Mock()
    mock_context.return_value = mock_server_context

    # Create thread with 2 existing messages
    existing_messages = [
        ThreadMessage(
            message_id=str(uuid.uuid4()),
            role="user",
            content=[ThreadTextContent(text="Message 1")],
        ),
        ThreadMessage(
            message_id=str(uuid.uuid4()),
            role="agent",
            content=[ThreadTextContent(text="Message 2")],
        ),
    ]
    existing_thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=existing_messages,
    )

    mock_storage.threads[thread_id] = existing_thread

    # Update with same 2 messages + 1 new message (total 3)
    all_messages = [
        {
            "message_id": existing_messages[0].message_id,
            "role": "user",
            "content": [{"kind": "text", "text": "Message 1"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
        {
            "message_id": existing_messages[1].message_id,
            "role": "agent",
            "content": [{"kind": "text", "text": "Message 2"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
        {
            "message_id": str(uuid.uuid4()),
            "role": "user",
            "content": [{"kind": "text", "text": "New message"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
    ]

    response = client.put(
        f"/threads/{thread_id}",
        json={
            "name": "Updated Thread",
            "agent_id": agent_id,
            "messages": all_messages,
        },
    )

    assert response.status_code == status.HTTP_200_OK

    # Verify OTEL counter was called only for the 1 new message
    mock_server_context.increment_counter.assert_called_with(
        "sema4ai.agent_server.messages",
        1,  # Only the new message should be counted
        {"agent_id": agent_id, "thread_id": thread_id},
    )


@patch("agent_platform.core.context.AgentServerContext.from_request")
def test_put_thread_no_new_messages(mock_context, client: TestClient, mock_storage: MockStorage):
    """Test that PUT endpoint doesn't count messages when none are new."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    mock_server_context = Mock()
    mock_context.return_value = mock_server_context

    # Create thread with 2 existing messages
    existing_messages = [
        ThreadMessage(
            message_id=str(uuid.uuid4()),
            role="user",
            content=[ThreadTextContent(text="Message 1")],
        ),
        ThreadMessage(
            message_id=str(uuid.uuid4()),
            role="agent",
            content=[ThreadTextContent(text="Message 2")],
        ),
    ]
    existing_thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=existing_messages,
    )

    mock_storage.threads[thread_id] = existing_thread

    # Update with only the same 2 existing messages (no new ones)
    same_messages = [
        {
            "message_id": existing_messages[0].message_id,
            "role": "user",
            "content": [{"kind": "text", "text": "Message 1"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
        {
            "message_id": existing_messages[1].message_id,
            "role": "agent",
            "content": [{"kind": "text", "text": "Message 2"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        },
    ]

    response = client.put(
        f"/threads/{thread_id}",
        json={
            "name": "Updated Thread Name Only",
            "agent_id": agent_id,
            "messages": same_messages,
        },
    )

    assert response.status_code == status.HTTP_200_OK

    # Verify OTEL counter was NOT called for messages (since new_message_count = 0)
    # Only check that increment_counter wasn't called with messages metric
    for call in mock_server_context.increment_counter.call_args_list:
        args, kwargs = call
        if args[0] == "sema4ai.agent_server.messages":
            pytest.fail("increment_counter should not be called for messages when no new messages")


@patch("agent_platform.core.context.AgentServerContext.from_request")
def test_put_thread_fewer_messages(mock_context, client: TestClient, mock_storage: MockStorage):
    """Test PUT endpoint when payload has fewer messages than existing thread."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    mock_server_context = Mock()
    mock_context.return_value = mock_server_context

    # Create thread with 3 existing messages
    existing_messages = [
        ThreadMessage(
            message_id=str(uuid.uuid4()), role="user", content=[ThreadTextContent(text="Msg 1")]
        ),
        ThreadMessage(
            message_id=str(uuid.uuid4()), role="agent", content=[ThreadTextContent(text="Msg 2")]
        ),
        ThreadMessage(
            message_id=str(uuid.uuid4()), role="user", content=[ThreadTextContent(text="Msg 3")]
        ),
    ]
    existing_thread = Thread(
        thread_id=thread_id,
        name="Test Thread",
        agent_id=agent_id,
        user_id="test_user",
        messages=existing_messages,
    )

    mock_storage.threads[thread_id] = existing_thread

    # Update with only 1 message (fewer than existing)
    fewer_messages = [
        {
            "message_id": existing_messages[0].message_id,
            "role": "user",
            "content": [{"kind": "text", "text": "Msg 1"}],
            "commited": True,
            "complete": True,
            "agent_metadata": {},
            "server_metadata": {},
        }
    ]

    response = client.put(
        f"/threads/{thread_id}",
        json={
            "name": "Updated Thread",
            "agent_id": agent_id,
            "messages": fewer_messages,
        },
    )

    assert response.status_code == status.HTTP_200_OK

    # Should not count any new messages since max(0, 1 - 3) = 0
    for call in mock_server_context.increment_counter.call_args_list:
        args, kwargs = call
        if args[0] == "sema4ai.agent_server.messages":
            pytest.fail(
                "increment_counter should not be called for messages when reducing message count"
            )


def test_patch_thread_empty_payload(client: TestClient, mock_storage: MockStorage):
    """Test patching with empty payload (no changes)."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    existing_thread = Thread(
        thread_id=thread_id,
        name="Original Name",
        agent_id=agent_id,
        user_id="test_user",
        messages=[],
    )

    mock_storage.threads[thread_id] = existing_thread

    # Patch with empty payload
    response = client.patch(f"/threads/{thread_id}", json={})

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    # Nothing should change
    assert thread_data["name"] == "Original Name"
    assert thread_data["agent_id"] == agent_id


def test_patch_thread_null_values(client: TestClient, mock_storage: MockStorage):
    """Test patching with explicit null values (should not update those fields)."""
    thread_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    existing_thread = Thread(
        thread_id=thread_id,
        name="Original Name",
        agent_id=agent_id,
        user_id="test_user",
        messages=[],
        metadata={"key": "value"},
    )

    mock_storage.threads[thread_id] = existing_thread

    # Patch with explicit None values - these fields should not be updated
    response = client.patch(
        f"/threads/{thread_id}",
        json={
            "name": "New Name",  # This should update
            "agent_id": None,  # This should not update (stays original)
            "metadata": None,  # This should not update (stays original)
        },
    )

    assert response.status_code == status.HTTP_200_OK
    thread_data = response.json()
    assert thread_data["name"] == "New Name"  # Updated
    assert thread_data["agent_id"] == agent_id  # Unchanged
    assert thread_data["metadata"]["key"] == "value"  # Unchanged
