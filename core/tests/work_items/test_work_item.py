from uuid import uuid4

import pytest

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemCallbackPayload,
    WorkItemStatus,
)


def test_work_item_callback_payload_smoke():
    """Basic smoke test for WorkItemCallbackPayload."""
    # Create a valid payload
    payload = WorkItemCallbackPayload(
        work_item_id="test-123",
        agent_id="agent-456",
        thread_id="thread-789",
        status=WorkItemStatus.COMPLETED,
        work_item_url="http://example.com/work-items/test-123",
        agent_name="Test Agent",  # Add agent_name
    )

    # Test model_dump() serializes correctly
    dumped = payload.model_dump()
    assert dumped == {
        "work_item_id": "test-123",
        "agent_id": "agent-456",
        "thread_id": "thread-789",
        "status": "COMPLETED",
        "work_item_url": "http://example.com/work-items/test-123",
        "agent_name": "Test Agent",  # Verify agent_name in dump
    }

    # Test model_validate() deserializes correctly
    validated = WorkItemCallbackPayload.model_validate(dumped)
    assert validated.work_item_id == payload.work_item_id
    assert validated.agent_id == payload.agent_id
    assert validated.thread_id == payload.thread_id
    assert validated.status == payload.status
    assert validated.work_item_url == payload.work_item_url
    assert validated.agent_name == payload.agent_name  # Verify agent_name after validation

    # Test validation errors
    with pytest.raises(ValueError, match="work_item_id is required"):
        WorkItemCallbackPayload.model_validate({})

    with pytest.raises(ValueError, match="agent_id is required"):
        WorkItemCallbackPayload.model_validate({"work_item_id": "test"})

    with pytest.raises(ValueError, match="thread_id is required"):
        WorkItemCallbackPayload.model_validate({"work_item_id": "test", "agent_id": "agent"})

    with pytest.raises(ValueError, match="agent_name is required"):
        WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test",
                "agent_id": "agent",
                "thread_id": "thread",
                "status": "COMPLETED",
                "work_item_url": "http://example.com",
            }
        )


def test_work_item_restart():
    """Test that the restart method resets the work item to the initial state."""
    user_msg = ThreadMessage(content=[ThreadTextContent(text="Initial request")], role="user")
    work_item = WorkItem(
        work_item_id="test-123",
        agent_id="agent-456",
        thread_id="thread-789",
        user_id="user-123",
        status=WorkItemStatus.NEEDS_REVIEW,
        initial_messages=[
            user_msg,
        ],
        messages=[
            user_msg,
            ThreadMessage(content=[ThreadTextContent(text="Agent response")], role="agent"),
        ],
    )
    original_messages = work_item.messages.copy()

    work_item.restart("user-456")
    assert work_item.status == WorkItemStatus.PENDING
    assert work_item.thread_id is None
    assert len(work_item.messages) == 1
    assert (
        work_item.messages[0].content[0].as_text_content() == user_msg.content[0].as_text_content()
    )
    assert work_item.completed_by is None
    assert work_item.status_updated_at is not None
    assert work_item.status_updated_by == "user-456"

    # when we reset, we must make sure that we got a new message_id or stuff gets really messy.
    assert work_item.messages[0].message_id != user_msg.message_id
    assert work_item.messages[0].message_id != original_messages[0].message_id


def test_work_item_to_initiate_stream_payload():
    """Test that the to_initiate_stream_payload method returns the correct payload."""
    initial_msg = ThreadMessage(content=[ThreadTextContent(text="Initial request")], role="user")
    file_msg = ThreadMessage(
        content=[ThreadTextContent(text="Uploaded [file.txt](https://example.com/file.txt)")],
        role="user",
    )

    work_item = WorkItem(
        work_item_id=str(uuid4()),
        agent_id=str(uuid4()),
        thread_id=str(uuid4()),
        user_id=str(uuid4()),
        status=WorkItemStatus.EXECUTING,
        initial_messages=[initial_msg],
        messages=[initial_msg, file_msg],
    )
    payload = work_item.to_initiate_stream_payload()
    assert payload.agent_id == work_item.agent_id
    assert payload.thread_id == work_item.thread_id
    assert payload.messages == work_item.messages, (
        "InitialStreamPayload should have all messages, not just initial_messages"
    )
    assert payload.metadata == {
        "from_work_item": True,
        "work_item_id": work_item.work_item_id,
    }
