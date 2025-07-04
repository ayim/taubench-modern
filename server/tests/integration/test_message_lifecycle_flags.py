"""Test the complete lifecycle of message flags during streaming and persistence."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.thread import ThreadAgentMessage, ThreadMessage
from agent_platform.core.thread.content import ThreadTextContent


@pytest.mark.asyncio
async def test_message_lifecycle_flags():
    """Test the complete lifecycle of complete and commited flags."""

    # 1. STREAMING PHASE: Message starts with both flags false
    message = ThreadAgentMessage(
        content=[],
        commited=False,
        complete=False,
    )

    assert message.commited is False, "New message should not be committed"
    assert message.complete is False, "New message should not be complete"

    # Simulate thread state
    mock_thread_state = AsyncMock()
    msg_with_state = ThreadMessageWithThreadState(message, mock_thread_state)

    # 2. CONTENT GENERATION: Add content during streaming
    msg_with_state.new_thought("Thinking about the response...")
    msg_with_state.append_content("Hello, ")
    msg_with_state.append_content("how can I help you?")

    # Still streaming
    assert message.commited is False, "Message should not be committed during streaming"
    assert message.complete is False, "Message should not be complete during streaming"

    # Content is also not complete
    for content in message.content:
        assert content.complete is False, "Content should not be complete during streaming"

    # 3. STREAMING COMPLETE: Mark the message as complete
    message.mark_complete()

    assert message.complete is True, "Message should be complete after mark_complete()"
    assert message.commited is False, "Message should not be committed yet"

    # All content should also be complete
    for content in message.content:
        assert content.complete is True, "All content should be complete after mark_complete()"

    # 4. COMMIT PHASE: Commit the message to storage
    await msg_with_state.commit()

    assert message.commited is True, "Message should be committed after commit()"
    assert message.complete is True, "Message should remain complete after commit()"

    # Verify commit was called on thread state
    mock_thread_state.commit_message.assert_called_once_with(message, ignore_websocket_errors=False)

    # 5. IMMUTABILITY: Cannot modify committed message
    with pytest.raises(ValueError, match="Cannot add content to a committed message"):
        msg_with_state.append_content("This should fail")

    with pytest.raises(ValueError, match="Cannot add content to a committed message"):
        msg_with_state.new_thought("This should also fail")


@pytest.mark.asyncio
async def test_storage_retrieval_sets_flags():
    """Test that messages retrieved from storage have both flags set to true."""

    # Mock storage response
    mock_row = {
        "message_id": str(uuid4()),
        "role": "agent",
        "content": [
            {"kind": "thought", "thought": "Thinking...", "complete": False},
            {"kind": "text", "text": "Hello!", "complete": False},
        ],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "agent_metadata": {},
        "server_metadata": {},
        "parent_run_id": None,
        # Note: commited and complete are NOT stored in DB
    }

    # Simulate what storage layer does
    mock_row["commited"] = True  # Storage sets this
    mock_row["complete"] = True  # Storage sets this

    # Create message from storage data
    retrieved_message = ThreadMessage.model_validate(mock_row)

    assert retrieved_message.commited is True, "Retrieved messages should have commited=True"
    assert retrieved_message.complete is True, "Retrieved messages should have complete=True"

    # Content items are also marked complete by model_validate
    for content in retrieved_message.content:
        assert content.complete is True, "Retrieved content should have complete=True"


def test_complete_without_commit():
    """Test that a message can be complete but not committed."""
    message = ThreadMessage(
        role="user",
        content=[ThreadTextContent(text="Test message")],
        complete=True,  # Finished generating
        commited=False,  # Not yet saved
    )

    # This is a valid state - message is done generating but not yet persisted
    assert message.complete is True
    assert message.commited is False

    # mark_complete ensures all content is also complete
    message.mark_complete()
    assert all(c.complete for c in message.content)


def test_commit_ensures_complete():
    """Test that commit() ensures the message is marked complete."""
    mock_thread_state = AsyncMock()
    message = ThreadAgentMessage(
        content=[ThreadTextContent(text="Test")],
        complete=False,  # Not complete yet
        commited=False,
    )

    msg_with_state = ThreadMessageWithThreadState(message, mock_thread_state)

    # Run commit synchronously for testing
    asyncio.run(msg_with_state.commit())

    # Commit should ensure both flags are true
    assert message.commited is True
    assert message.complete is True
    assert all(c.complete for c in message.content)

    # Verify commit was called with default parameters
    mock_thread_state.commit_message.assert_called_once_with(message, ignore_websocket_errors=False)
