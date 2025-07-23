from uuid import uuid4

import pytest

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemCallback,
    WorkItemCallbackPayload,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)


def test_work_item_model_dump_includes_work_item_url():
    """Test that WorkItem.model_dump() includes work_item_url field."""
    work_item = WorkItem(
        work_item_id="test-123",
        user_id="system-user-123",
        created_by="user-123",
        agent_id="agent-789",
        thread_id="thread-012",
        status=WorkItemStatus.PENDING,
        work_item_url="http://example.com/workspace/agent-789/thread-012",
    )

    dumped = work_item.model_dump()
    assert "work_item_url" in dumped
    assert dumped["work_item_url"] == "http://example.com/workspace/agent-789/thread-012"


def test_work_item_model_validate_handles_work_item_url():
    """Test that WorkItem.model_validate() properly handles work_item_url field."""
    data = {
        "work_item_id": "test-123",
        "user_id": "system-user-123",
        "created_by": "user-123",
        "agent_id": "agent-789",
        "thread_id": "thread-012",
        "status": "PENDING",
        "work_item_url": "http://example.com/workspace/agent-789/thread-012",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "status_updated_at": "2023-01-01T00:00:00Z",
        "status_updated_by": "SYSTEM",
        "messages": [],
        "payload": {},
        "callbacks": [],
    }

    work_item = WorkItem.model_validate(data)
    assert work_item.work_item_url == "http://example.com/workspace/agent-789/thread-012"


def test_work_item_model_validate_handles_none_work_item_url():
    """Test that WorkItem.model_validate() handles None work_item_url field."""
    data = {
        "work_item_id": "test-123",
        "user_id": "system-user-123",
        "created_by": "user-123",
        "agent_id": "agent-789",
        "thread_id": "thread-012",
        "status": "PENDING",
        "work_item_url": None,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "status_updated_at": "2023-01-01T00:00:00Z",
        "status_updated_by": "SYSTEM",
        "messages": [],
        "payload": {},
        "callbacks": [],
    }

    work_item = WorkItem.model_validate(data)
    assert work_item.work_item_url is None


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
        user_id="system-user-123",
        created_by="user-123",
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

    work_item.restart()
    assert work_item.status == WorkItemStatus.PENDING
    assert work_item.thread_id is None
    assert len(work_item.messages) == 1
    assert (
        work_item.messages[0].content[0].as_text_content() == user_msg.content[0].as_text_content()
    )
    assert work_item.completed_by is None
    assert work_item.status_updated_at is not None
    assert work_item.status_updated_by == WorkItemStatusUpdatedBy.HUMAN

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
        created_by=str(uuid4()),
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


def test_work_item_model_validate_field_parsing():
    """Test that the model_validate method properly parses various field types."""
    from datetime import UTC, datetime
    from uuid import uuid4

    # Create test data with string values that need parsing
    test_data = {
        "work_item_id": str(uuid4()),
        "user_id": str(uuid4()),
        "created_by": str(uuid4()),
        "agent_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "status": "COMPLETED",  # String -> WorkItemStatus enum
        "completed_by": "AGENT",  # String -> WorkItemCompletedBy enum
        "created_at": "2024-01-15T10:30:00+00:00",  # String -> datetime
        "updated_at": "2024-01-15T11:30:00+00:00",  # String -> datetime
        "status_updated_at": "2024-01-15T12:30:00+00:00",  # String -> datetime
        "status_updated_by": "AGENT",  # String -> WorkItemStatusUpdatedBy enum
        "messages": [
            {
                "message_id": str(uuid4()),
                "role": "user",
                "content": [{"kind": "text", "text": "Hello"}],
                "created_at": "2024-01-15T10:30:00+00:00",
            }
        ],
        "initial_messages": [
            {
                "message_id": str(uuid4()),
                "role": "user",
                "content": [{"kind": "text", "text": "Initial"}],
                "created_at": "2024-01-15T10:29:00+00:00",
            }
        ],
        "callbacks": [
            {
                "url": "https://example.com/callback",
                "on_status": "NEEDS_REVIEW",  # String -> WorkItemStatus enum
                "signature_secret": "secret123",
            }
        ],
        "payload": {"key": "value"},
    }

    # Test that model_validate properly parses all fields
    work_item = WorkItem.model_validate(test_data)

    # Test enum parsing
    assert work_item.status == WorkItemStatus.COMPLETED
    assert isinstance(work_item.status, WorkItemStatus)
    assert work_item.completed_by == WorkItemCompletedBy.AGENT
    assert isinstance(work_item.completed_by, WorkItemCompletedBy)

    # Test datetime parsing
    assert isinstance(work_item.created_at, datetime)
    assert isinstance(work_item.updated_at, datetime)
    assert isinstance(work_item.status_updated_at, datetime)
    assert work_item.created_at.tzinfo == UTC

    # Test nested object parsing
    assert len(work_item.messages) == 1
    assert isinstance(work_item.messages[0], ThreadMessage)
    assert len(work_item.initial_messages) == 1
    assert isinstance(work_item.initial_messages[0], ThreadMessage)
    assert len(work_item.callbacks) == 1
    assert isinstance(work_item.callbacks[0], WorkItemCallback)
    assert work_item.callbacks[0].on_status == WorkItemStatus.NEEDS_REVIEW

    # Test with None/missing optional fields
    minimal_data = {
        "work_item_id": "test-123",
        "user_id": "user-456",
        "created_by": "user-123",
    }
    work_item_minimal = WorkItem.model_validate(minimal_data)
    assert work_item_minimal.completed_by is None
    assert work_item_minimal.agent_id is None
    assert work_item_minimal.thread_id is None
    assert work_item_minimal.status == WorkItemStatus.PENDING  # Default value


def test_work_item_subject_field():
    """Test that the user_subject field works correctly in the WorkItem model."""
    work_item = WorkItem(
        work_item_id="test-123",
        user_id="user-456",
        agent_id="agent-789",
        user_subject="test-user-user_subject",
        messages=[],
        payload={"test": "data"},
    )

    # Test that user_subject is accessible
    assert work_item.user_subject == "test-user-user_subject"

    # Test model_dump includes user_subject field
    serialized = work_item.model_dump()
    assert "user_subject" in serialized
    assert serialized["user_subject"] == "test-user-user_subject"

    # Test model_validate with user_subject field
    data = {
        "work_item_id": "test-456",
        "user_id": "user-789",
        "agent_id": "agent-123",
        "user_subject": "another-user-user_subject",
        "messages": [],
        "payload": {},
        "status": "PENDING",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "status_updated_at": "2023-01-01T00:00:00Z",
        "status_updated_by": "HUMAN",
        "initial_messages": [],
        "callbacks": [],
    }
    validated_item = WorkItem.model_validate(data)
    assert validated_item.user_subject == "another-user-user_subject"

    # Test with None user_subject
    work_item_no_subject = WorkItem(
        work_item_id="test-789",
        user_id="user-123",
        agent_id="agent-456",
        user_subject=None,
        messages=[],
        payload={},
    )
    assert work_item_no_subject.user_subject is None

    serialized_none = work_item_no_subject.model_dump()
    assert "user_subject" in serialized_none
    assert serialized_none["user_subject"] is None
