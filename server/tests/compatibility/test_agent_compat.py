from datetime import UTC, datetime

from agent_platform.core.agent import Agent, AgentArchitecture, QuestionGroup
from agent_platform.core.runbook import Runbook
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat


def create_agent(welcome_message: str, question_groups: list[QuestionGroup]):
    return Agent(
        agent_id="agent-compat-1",
        user_id="user-1",
        name="CompatAgent",
        description="desc",
        runbook_structured=Runbook(raw_text="Welcome!", content=[]),
        version="1.0.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        platform_configs=[],
        action_packages=[],
        mcp_servers=[],
        agent_architecture=AgentArchitecture(name="default", version="1.0.0"),
        question_groups=question_groups,
        observability_configs=[],
        extra={"welcome-message": welcome_message},
        mode="conversational",
    )


def test_agent_compat_welcome_message():
    agent = create_agent(
        welcome_message="Hello, user!",
        question_groups=[],
    )
    compat = AgentCompat.from_agent(agent)
    assert "welcome_message" in compat.metadata
    assert compat.metadata["welcome_message"] == "Hello, user!"


def test_agent_compat_question_groups():
    qgroups = [
        QuestionGroup(title="Group 1", questions=["Q1", "Q2"]),
        QuestionGroup(title="Group 2", questions=["Q3"]),
    ]
    agent = create_agent(
        welcome_message="Welcome!",
        question_groups=qgroups,
    )
    compat = AgentCompat.from_agent(agent)
    assert "question_groups" in compat.metadata
    assert compat.metadata["question_groups"] == qgroups
    assert compat.question_groups == qgroups
    # Check serialization
    for group in compat.metadata["question_groups"]:
        assert hasattr(group, "title")
        assert hasattr(group, "questions")
