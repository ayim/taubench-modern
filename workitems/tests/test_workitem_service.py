import pytest
from sqlalchemy.orm import Session

from agent_platform.workitems.models import (
    CreateWorkItemPayload,
    WorkItemMessage,
    WorkItemMessageContent,
)
from agent_platform.workitems.services.workitem import AgentValidationError, WorkItemService


class TestWorkItemService:
    """Test the WorkItemService business logic."""

    @pytest.mark.asyncio
    async def test_service_create_success(
        self, require_docker, session: Session, mock_agent_client
    ):
        """Test successful work item creation through service."""
        service = WorkItemService(session, mock_agent_client)

        payload = CreateWorkItemPayload(
            agent_id="test-agent-1",
            messages=[
                WorkItemMessage(
                    role="user",
                    content=[WorkItemMessageContent(kind="text", text="Service test message")],
                )
            ],
            payload={"service_test": True},
        )

        work_item = await service.create(payload)

        assert work_item.agent_id == "test-agent-1"
        assert work_item.thread_id, "did not get a thread id"
        assert len(work_item.messages) == 1
        assert work_item.messages[0].content[0].text == "Service test message"
        assert work_item.payload["service_test"] is True
        assert work_item.work_item_id is not None

    @pytest.mark.asyncio
    async def test_service_create_invalid_agent(
        self, require_docker, session: Session, mock_agent_client
    ):
        """Test work item creation with invalid agent through service."""
        service = WorkItemService(session, mock_agent_client)

        payload = CreateWorkItemPayload(agent_id="invalid-agent", messages=[], payload={})

        with pytest.raises(AgentValidationError) as exc_info:
            await service.create(payload)

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_describe(self, session: Session, mock_agent_client):
        """Test work item description through service."""
        service = WorkItemService(session, mock_agent_client)

        # First create a work item
        payload = CreateWorkItemPayload(
            agent_id="test-agent-2",
            messages=[],
            payload={"describe_test": True},
        )

        created_item = await service.create(payload)
        work_item_id = created_item.work_item_id

        # Then describe it
        described_item = await service.describe(work_item_id)

        assert described_item is not None
        assert described_item.work_item_id == work_item_id
        assert described_item.agent_id == "test-agent-2"
        assert described_item.thread_id, "did not get a thread id"
        assert described_item.payload["describe_test"] is True

    @pytest.mark.asyncio
    async def test_service_describe_nonexistent(self, session: Session, mock_agent_client):
        """Test describing a nonexistent work item through service."""
        service = WorkItemService(session, mock_agent_client)

        result = await service.describe("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_service_list(self, require_docker, session: Session, mock_agent_client):
        """Test listing work items through service."""
        service = WorkItemService(session, mock_agent_client)

        # Create a few work items
        actual_thread_ids = []
        for i in range(3):
            payload = CreateWorkItemPayload(
                agent_id="test-agent-1",
                messages=[],
                payload={"list_index": i},
            )
            work_item = await service.create(payload)
            actual_thread_ids.append(work_item.thread_id)

        # List items
        items = await service.list()

        assert len(items) == 3
        # Verify our items are in the list
        list_thread_ids = {item.thread_id for item in items}
        for actual_thread_id in actual_thread_ids:
            assert actual_thread_id in list_thread_ids

    @pytest.mark.asyncio
    async def test_service_list_with_limit(
        self, require_docker, session: Session, mock_agent_client
    ):
        """Test listing work items with limit through service."""
        service = WorkItemService(session, mock_agent_client)

        # Create several work items
        for _ in range(5):
            payload = CreateWorkItemPayload(agent_id="test-agent-1", messages=[], payload={})
            await service.create(payload)

        # List with limit
        items = await service.list(limit=2)
        assert len(items) == 2
