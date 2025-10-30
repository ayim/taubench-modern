"""Tests for CreateWorkItemPayload validation and functionality."""

from agent_platform.core.payloads.create_work_item import CreateWorkItemPayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent


def test_create_work_item_payload_with_name():
    """Test creating a payload with work_item_name."""
    payload = CreateWorkItemPayload(
        agent_id="agent-123",
        work_item_name="SNOW12345",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Test message")],
            )
        ],
        payload={"test": "data"},
    )

    assert payload.work_item_name == "SNOW12345"
    assert payload.agent_id == "agent-123"


def test_create_work_item_payload_to_work_item_with_whitespace():
    """Test that to_work_item method properly handles work_item_name whitespace."""
    # Test whitespace trimming in WorkItem creation
    payload = CreateWorkItemPayload(
        agent_id="agent-123",
        work_item_name="  INVABC123  ",
        messages=[],
        payload={},
    )

    work_item = CreateWorkItemPayload.to_work_item(
        payload=payload,
        owner_user_id="owner-456",
        created_by_user_id="creator-789",
    )

    assert work_item.work_item_name == "INVABC123"

    # Test empty string becomes None in WorkItem creation
    payload_empty = CreateWorkItemPayload(
        agent_id="agent-123",
        work_item_name="   ",
        messages=[],
        payload={},
    )

    work_item_empty = CreateWorkItemPayload.to_work_item(
        payload=payload_empty,
        owner_user_id="owner-456",
        created_by_user_id="creator-789",
    )

    assert work_item_empty.work_item_name == f"Work Item {work_item_empty.work_item_id}"


def test_create_work_item_payload_to_work_item():
    """Test that to_work_item method properly handles work_item_name."""
    payload = CreateWorkItemPayload(
        agent_id="agent-123",
        work_item_name="TICKET789",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Test message")],
            )
        ],
        payload={"test": "data"},
    )

    work_item = CreateWorkItemPayload.to_work_item(
        payload=payload,
        owner_user_id="owner-456",
        created_by_user_id="creator-789",
    )

    assert work_item.work_item_name == "TICKET789"
    assert work_item.agent_id == "agent-123"
    assert work_item.user_id == "owner-456"
    assert work_item.created_by == "creator-789"


def test_create_work_item_payload_without_name():
    """Test creating a payload without work_item_name."""
    payload = CreateWorkItemPayload(
        agent_id="agent-123",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Test message")],
            )
        ],
        payload={"test": "data"},
    )

    assert payload.work_item_name is None, "The payload may have an absent name"

    work_item = CreateWorkItemPayload.to_work_item(
        payload=payload,
        owner_user_id="owner-456",
        created_by_user_id="creator-789",
    )

    assert work_item.work_item_name == f"Work Item {work_item.work_item_id}", (
        "the real work item may not have an absent name"
    )
