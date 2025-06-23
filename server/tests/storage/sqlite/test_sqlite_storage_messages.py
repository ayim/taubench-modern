from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.agent import Agent
from agent_platform.core.thread import Thread, ThreadMessage, ThreadTextContent
from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_get_messages_by_parent_run_id(
    storage: SQLiteStorage,
    sample_user_id: str,
    sample_agent: Agent,
) -> None:
    """Ensure messages filtered by parent_run_id are returned only to the correct user."""

    # Create an owner user (non-system) and an agent owned by them.
    owner_user, _ = await storage.get_or_create_user(sub="tenant:testing:user:owner")
    parent_run_id = str(uuid4())

    owned_agent = Agent.model_validate(
        sample_agent.model_dump()
        | {
            "agent_id": str(uuid4()),
            "user_id": owner_user.user_id,
            "name": "Parent-Run Agent",
        }
    )

    thread = Thread(
        thread_id=str(uuid4()),
        user_id=owner_user.user_id,
        agent_id=owned_agent.agent_id,
        name="Parent Run Message Test",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello from user")],
                parent_run_id=parent_run_id,
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="Hello from agent")],
                parent_run_id=parent_run_id,
            ),
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Unrelated message")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={},
    )

    # Persist the agent and thread with the owner user.
    await storage.upsert_agent(owner_user.user_id, owned_agent)
    await storage.upsert_thread(owner_user.user_id, thread)

    messages = await storage.get_messages_by_parent_run_id(owner_user.user_id, parent_run_id)
    assert len(messages) == 2
    assert all(m.parent_run_id == parent_run_id for m in messages)
    assert messages[0].role == "user"
    assert messages[1].role == "agent"

    # Cross-tenant user should not see the messages
    other_user, _ = await storage.get_or_create_user(sub="tenant:other:user")
    invisible = await storage.get_messages_by_parent_run_id(other_user.user_id, parent_run_id)
    assert invisible == []
