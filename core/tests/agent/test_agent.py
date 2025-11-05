from datetime import UTC, datetime

from agent_platform.core.agent.agent import (
    Agent,
    AgentArchitecture,
    AgentUserInterface,
    Runbook,
)


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


def test_agent_settings():
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
    )

    assert agent.agent_settings() == {}

    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={"agent_settings": {"key": "value"}},
    )
    assert agent.agent_settings() == {"key": "value"}


def test_get_user_interfaces():
    # Test with no user_interfaces
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
    )
    assert agent.get_user_interfaces() == []

    # Test with empty user_interfaces
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={"agent_settings": {"user_interfaces": ""}},
    )
    assert agent.get_user_interfaces() == []

    # Test with single valid user interface (string format)
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={"agent_settings": {"user_interfaces": "di-parse-only"}},
    )
    assert agent.get_user_interfaces() == [AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY]

    # Test with multiple valid user interfaces (string format)
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={"agent_settings": {"user_interfaces": "di-parse-only,di-create-data-model"}},
    )
    assert agent.get_user_interfaces() == [
        AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY,
        AgentUserInterface.DOCUMENT_INTELLIGENCE_CREATE_DATA_MODEL,
    ]

    # Test with invalid user interface (should be skipped with warning)
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={"agent_settings": {"user_interfaces": "invalid-interface"}},
    )
    assert agent.get_user_interfaces() == []

    # Test with mix of valid and invalid user interfaces (string format)
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={
            "agent_settings": {
                "user_interfaces": "di-parse-only,invalid-interface,di-create-data-model"
            }
        },
    )
    assert agent.get_user_interfaces() == [
        AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY,
        AgentUserInterface.DOCUMENT_INTELLIGENCE_CREATE_DATA_MODEL,
    ]

    # Test with mix of valid and invalid user interfaces (list format)
    agent = Agent(
        name="Agent Smith",
        description="A helpful agent.",
        user_id="user-123",
        runbook_structured=Runbook(raw_text="Do work", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="base", version="1"),
        extra={
            "agent_settings": {
                "user_interfaces": [
                    AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY,
                    "invalid-interface",
                ]
            }
        },
    )
    assert agent.get_user_interfaces() == [AgentUserInterface.DOCUMENT_INTELLIGENCE_PARSE_ONLY]
