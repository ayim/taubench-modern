import pytest

from agent_platform.core.work_items.work_item import WorkItemCallbackPayload, WorkItemStatus


def test_work_item_callback_payload_smoke():
    """Basic smoke test for WorkItemCallbackPayload."""
    # Create a valid payload
    payload = WorkItemCallbackPayload(
        work_item_id="test-123",
        agent_id="agent-456",
        thread_id="thread-789",
        status=WorkItemStatus.COMPLETED,
        work_item_url="http://example.com/work-items/test-123",
    )

    # Test model_dump() serializes correctly
    dumped = payload.model_dump()
    assert dumped == {
        "work_item_id": "test-123",
        "agent_id": "agent-456",
        "thread_id": "thread-789",
        "status": "COMPLETED",
        "work_item_url": "http://example.com/work-items/test-123",
    }

    # Test model_validate() deserializes correctly
    validated = WorkItemCallbackPayload.model_validate(dumped)
    assert validated.work_item_id == payload.work_item_id
    assert validated.agent_id == payload.agent_id
    assert validated.thread_id == payload.thread_id
    assert validated.status == payload.status
    assert validated.work_item_url == payload.work_item_url

    # Test validation errors
    with pytest.raises(ValueError, match="work_item_id is required"):
        WorkItemCallbackPayload.model_validate({})

    with pytest.raises(ValueError, match="agent_id is required"):
        WorkItemCallbackPayload.model_validate({"work_item_id": "test"})

    with pytest.raises(ValueError, match="thread_id is required"):
        WorkItemCallbackPayload.model_validate({"work_item_id": "test", "agent_id": "agent"})
