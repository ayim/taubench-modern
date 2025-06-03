import uuid

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
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
        return self.threads.get(thread_id)

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
