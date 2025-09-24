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
