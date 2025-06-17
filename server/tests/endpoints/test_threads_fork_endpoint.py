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
    """Mock storage class for testing threads fork API endpoint."""

    def __init__(self):
        self.threads: dict[str, Thread] = {}
        self.users: dict[str, User] = {}

    async def get_thread(self, user_id: str, thread_id: str) -> Thread | None:
        return self.threads.get(thread_id)

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        self.threads[thread.thread_id] = thread

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        if sub not in self.users:
            self.users[sub] = User(
                user_id=str(uuid.uuid4()),
                sub=sub,
            )
            return self.users[sub], True
        return self.users[sub], False

    async def list_threads_for_agent(self, user_id: str, agent_id: str) -> list[Thread]:
        """List all threads for a specific agent."""
        return [
            thread
            for thread in self.threads.values()
            if thread.agent_id == agent_id and thread.user_id == user_id
        ]


@pytest.fixture
def mock_storage():
    """Create mock storage instance."""
    return MockStorage()


@pytest.fixture
def test_user():
    """Create a mock user for testing."""
    return User(user_id=str(uuid.uuid4()), sub="static-default-user-id")


@pytest.fixture
def test_app(mock_storage, test_user):
    """Create test FastAPI app with mocked dependencies."""
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


@pytest.fixture
def sample_thread(mock_storage, test_user):
    """Create a sample thread with multiple messages."""
    thread = Thread(
        thread_id=str(uuid.uuid4()),
        user_id=test_user.user_id,
        agent_id=str(uuid.uuid4()),
        name="Test Thread",
        messages=[
            ThreadMessage(
                message_id="msg-1",
                role="user",
                content=[ThreadTextContent(text="Hello, I need help with Python")],
            ),
            ThreadMessage(
                message_id="msg-2",
                role="agent",
                content=[ThreadTextContent(text="I'd be happy to help with Python!")],
            ),
            ThreadMessage(
                message_id="msg-3",
                role="user",
                content=[ThreadTextContent(text="Can you explain decorators?")],
            ),
            ThreadMessage(
                message_id="msg-4",
                role="agent",
                content=[
                    ThreadTextContent(
                        text="Decorators are functions that modify other functions..."
                    )
                ],
            ),
            ThreadMessage(
                message_id="msg-5",
                role="user",
                content=[ThreadTextContent(text="Thanks! Now can you show an example?")],
            ),
            ThreadMessage(
                message_id="msg-6",
                role="agent",
                content=[ThreadTextContent(text="Here's a simple decorator example...")],
            ),
        ],
        metadata={"original": "metadata"},
    )
    mock_storage.threads[thread.thread_id] = thread
    return thread


def test_fork_thread_success(client: TestClient, sample_thread: Thread):
    """Test successful thread forking."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3"},  # Fork at the second user message
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()

    # Check the forked thread properties
    assert forked_thread["name"] == "Test Thread (1)"
    assert forked_thread["agent_id"] == sample_thread.agent_id
    assert forked_thread["user_id"] == sample_thread.user_id

    # Messages should not be returned
    assert forked_thread["messages"] == []

    # Check metadata
    assert forked_thread["metadata"]["forked_from_thread_id"] == sample_thread.thread_id
    assert forked_thread["metadata"]["forked_at_message_id"] == "msg-3"
    assert forked_thread["metadata"]["original"] == "metadata"


def test_fork_thread_at_first_message(client: TestClient, sample_thread: Thread):
    """Test forking at the first message (should fail)."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-1"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.json()["detail"]
        == "Cannot fork at the first message - no previous messages to include"
    )


def test_fork_thread_at_last_user_message(client: TestClient, sample_thread: Thread):
    """Test forking at the last user message."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-5"},
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()

    # Messages should not be returned
    assert forked_thread["messages"] == []
    assert forked_thread["name"] == "Test Thread (1)"


def test_fork_thread_invalid_message_id(client: TestClient, sample_thread: Thread):
    """Test forking with non-existent message ID."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "non-existent-msg"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Message not found in thread"


def test_fork_thread_agent_message(client: TestClient, sample_thread: Thread):
    """Test forking at an agent message (should fail)."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-2"},  # This is an agent message
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Fork point must be a human message"


def test_fork_thread_not_found(client: TestClient):
    """Test forking a non-existent thread."""
    response = client.post(
        "/threads/non-existent-thread/fork",
        json={"message_id": "msg-1"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Thread not found"


def test_fork_thread_creates_new_thread_id(
    client: TestClient, sample_thread: Thread, mock_storage: MockStorage
):
    """Test that forking creates a new thread with a different ID."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3"},
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()

    # Check that a new thread ID was generated
    assert forked_thread["thread_id"] != sample_thread.thread_id

    # Check that the forked thread was saved to storage
    assert forked_thread["thread_id"] in mock_storage.threads
    saved_thread = mock_storage.threads[forked_thread["thread_id"]]
    assert saved_thread.name == "Test Thread (1)"
    # The saved thread should have the messages (2 messages before msg-3)
    assert len(saved_thread.messages) == 2


def test_fork_thread_increments_number(
    client: TestClient, sample_thread: Thread, mock_storage: MockStorage
):
    """Test that forking increments the number when multiple forks exist."""
    # Create first fork
    response1 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3"},
    )
    assert response1.status_code == status.HTTP_200_OK
    forked_thread1 = response1.json()
    assert forked_thread1["name"] == "Test Thread (1)"

    # Create second fork
    response2 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-5"},
    )
    assert response2.status_code == status.HTTP_200_OK
    forked_thread2 = response2.json()
    assert forked_thread2["name"] == "Test Thread (2)"

    # Create third fork
    response3 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3"},
    )
    assert response3.status_code == status.HTTP_200_OK
    forked_thread3 = response3.json()
    assert forked_thread3["name"] == "Test Thread (3)"


def test_fork_thread_with_existing_numbered_name(
    client: TestClient, mock_storage: MockStorage, test_user
):
    """Test forking a thread that already has a numbered suffix."""
    # Create a thread with a numbered name
    numbered_thread = Thread(
        thread_id=str(uuid.uuid4()),
        user_id=test_user.user_id,
        agent_id=str(uuid.uuid4()),
        name="My Thread (2)",
        messages=[
            ThreadMessage(
                message_id="msg-1",
                role="user",
                content=[ThreadTextContent(text="First message")],
            ),
            ThreadMessage(
                message_id="msg-2",
                role="agent",
                content=[ThreadTextContent(text="Response")],
            ),
            ThreadMessage(
                message_id="msg-3",
                role="user",
                content=[ThreadTextContent(text="Second message")],
            ),
        ],
        metadata={},
    )
    mock_storage.threads[numbered_thread.thread_id] = numbered_thread

    # Fork the numbered thread
    response = client.post(
        f"/threads/{numbered_thread.thread_id}/fork",
        json={"message_id": "msg-3"},
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()
    # Should create "My Thread (2) (1)" since we're forking from "My Thread (2)"
    assert forked_thread["name"] == "My Thread (2) (1)"


def test_fork_thread_with_custom_name(client: TestClient, sample_thread: Thread):
    """Test forking a thread with a custom name."""
    custom_name = "My Custom Fork Name"
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3", "name": custom_name},
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()
    assert forked_thread["name"] == custom_name


def test_fork_thread_with_empty_name_uses_default(client: TestClient, sample_thread: Thread):
    """Test that providing an empty name falls back to auto-generated name."""
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3", "name": None},
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()
    # Should use auto-generated name
    assert forked_thread["name"] == "Test Thread (1)"


def test_fork_thread_custom_name_with_multiple_forks(client: TestClient, sample_thread: Thread):
    """Test mixing custom names and auto-generated names."""
    # First fork with custom name
    response1 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3", "name": "Custom Fork 1"},
    )
    assert response1.status_code == status.HTTP_200_OK
    assert response1.json()["name"] == "Custom Fork 1"

    # Second fork with auto-generated name
    response2 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-5"},
    )
    assert response2.status_code == status.HTTP_200_OK
    assert response2.json()["name"] == "Test Thread (1)"

    # Third fork with another custom name
    response3 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3", "name": "Another Custom Fork"},
    )
    assert response3.status_code == status.HTTP_200_OK
    assert response3.json()["name"] == "Another Custom Fork"

    # Fourth fork with auto-generated name should be (2)
    response4 = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-5"},
    )
    assert response4.status_code == status.HTTP_200_OK
    assert response4.json()["name"] == "Test Thread (2)"


def test_fork_thread_creates_new_message_ids(
    client: TestClient, sample_thread: Thread, mock_storage: MockStorage
):
    """Test that forked threads have new message IDs, not the original ones."""
    # Get original message IDs
    original_message_ids = [msg.message_id for msg in sample_thread.messages[:2]]

    # Fork the thread
    response = client.post(
        f"/threads/{sample_thread.thread_id}/fork",
        json={"message_id": "msg-3"},  # Fork at the second user message
    )

    assert response.status_code == status.HTTP_200_OK
    forked_thread = response.json()

    # Get the forked thread from storage to check messages
    saved_thread = mock_storage.threads[forked_thread["thread_id"]]
    assert len(saved_thread.messages) == 2  # Should have 2 messages before msg-3

    # Check that all message IDs are new (different from originals)
    forked_message_ids = [msg.message_id for msg in saved_thread.messages]

    # Ensure no message ID from the forked thread matches the original
    for forked_id in forked_message_ids:
        assert forked_id not in original_message_ids

    # Ensure all forked message IDs are unique
    assert len(forked_message_ids) == len(set(forked_message_ids))

    # Verify content is preserved (check roles match)
    assert saved_thread.messages[0].role == sample_thread.messages[0].role
    assert saved_thread.messages[1].role == sample_thread.messages[1].role
