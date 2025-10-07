from datetime import UTC, datetime

from agent_platform.core.agent.agent import Agent


def test_model_validate_ignores_unknown_fields() -> None:
    agent = Agent.model_validate(
        {
            "name": "Agent Smith",
            "description": "A helpful agent.",
            "user_id": "user-123",
            "runbook_structured": {"raw_text": "Do work", "content": []},
            "version": "1.0.0",
            "platform_configs": [],
            "agent_architecture": {"name": "base", "version": "1"},
            "unexpected_column": "ignored",
        }
    )

    assert agent.name == "Agent Smith"
    assert agent.agent_architecture.name == "base"
    assert not hasattr(agent, "unexpected_column")


def test_model_validate_sets_runbook_updated_from_agent_timestamp() -> None:
    agent_updated = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)

    agent = Agent.model_validate(
        {
            "name": "Agent Smith",
            "description": "A helpful agent.",
            "user_id": "user-123",
            "runbook_structured": {"raw_text": "Do work", "content": []},
            "version": "1.0.0",
            "platform_configs": [],
            "agent_architecture": {"name": "base", "version": "1"},
            "updated_at": agent_updated.isoformat(),
        }
    )

    assert agent.runbook_structured.updated_at == agent_updated


def test_model_validate_sets_runbook_updated_when_timestamp_missing() -> None:
    before = datetime.now(UTC)

    agent = Agent.model_validate(
        {
            "name": "Agent Smith",
            "description": "A helpful agent.",
            "user_id": "user-123",
            "runbook_structured": {"raw_text": "Do work", "content": []},
            "version": "1.0.0",
            "platform_configs": [],
            "agent_architecture": {"name": "base", "version": "1"},
        }
    )

    after = datetime.now(UTC)

    runbook_updated_at = agent.runbook_structured.updated_at
    assert before <= runbook_updated_at <= after
    assert runbook_updated_at.tzinfo == UTC
