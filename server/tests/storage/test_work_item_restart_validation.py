"""Test work item restart validation with real storage.

This test module uses real storage (SQLite or Postgres) to verify
that the restart operation correctly validates state transitions
after cancellation attempts.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.user import User
from agent_platform.core.utils.secret_str import SecretString
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_restart_executing_work_item_validates_updated_status(
    storage: "SQLiteStorage | PostgresStorage",
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that restart validates against the updated work item status after cancellation.

    This test verifies the fix for a bug where restarting an EXECUTING work item
    would validate the state transition using the stale EXECUTING status instead of
    the updated status after cancellation (e.g., CANCELLED).

    Before the fix:
    1. Work item is in EXECUTING status
    2. restart_work_item() calls cancel_work_item_execution()
    3. Cancellation updates status to CANCELLED in the database
    4. BUT the in-memory work_item object still has EXECUTING status
    5. State transition validation checks EXECUTING -> PENDING (wrong!)

    After the fix:
    1. Work item is in EXECUTING status
    2. restart_work_item() calls cancel_work_item_execution()
    3. Cancellation updates status to CANCELLED in the database
    4. Code re-fetches work item from storage to get updated status
    5. State transition validation checks CANCELLED -> PENDING (correct!)
    """
    from agent_platform.server.work_items import rest as rest_module

    # Get or create system user
    system_user_id = await storage.get_system_user_id()

    # Create a test agent
    agent = Agent(
        user_id=system_user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Agent for restart validation",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-package",
                organization="test-org",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
            version="1.0.0",
        ),
        question_groups=[],
        observability_configs=[],
        platform_configs=[],
        extra={},
    )
    await storage.upsert_agent(system_user_id, agent)

    # Create a work item in EXECUTING status
    work_item = WorkItem(
        work_item_id=str(uuid4()),
        user_id=system_user_id,
        created_by=system_user_id,
        agent_id=agent.agent_id,
        status=WorkItemStatus.EXECUTING,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Test request")],
            ),
        ],
        payload={},
    )
    await storage.create_work_item(work_item)

    # Mock the WorkItemsService to simulate successful cancellation
    # that changes the work item status to CANCELLED
    class StubWorkItemsService:
        async def cancel_work_item_execution(self, work_item_id: str) -> bool:
            # Simulate the cancellation changing the status to CANCELLED in the database
            item = await storage.get_work_item(work_item_id)
            if item:
                item.status = WorkItemStatus.CANCELLED
                item.status_updated_by = WorkItemStatusUpdatedBy.SYSTEM
                item.status_updated_at = datetime.now(UTC)
                await storage.update_work_item(item)
            return True

    stub_service = StubWorkItemsService()
    monkeypatch.setattr(
        "agent_platform.server.work_items.service.WorkItemsService.get_instance",
        classmethod(lambda cls: stub_service),
    )

    # Create a user for the restart call
    user = User(user_id=system_user_id, sub="test@test.com")

    # Call restart_work_item directly
    result = await rest_module.restart_work_item(
        work_item_id=work_item.work_item_id,
        user=user,
        storage=storage,
    )

    # Verify the restart succeeded
    assert result is not None
    assert result.status == WorkItemStatus.PENDING

    # Verify the work item was actually updated in storage
    updated_item = await storage.get_work_item(work_item.work_item_id)
    assert updated_item is not None
    assert updated_item.status == WorkItemStatus.PENDING
