from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent_platform.core.actions import ActionPackage
from agent_platform.core.agent import (
    Agent,
    AgentArchitecture,
    ObservabilityConfig,
    QuestionGroup,
)
from agent_platform.core.runbook import Runbook
from agent_platform.core.thread import Thread, ThreadMessage, ThreadTextContent
from agent_platform.core.utils import SecretString


@pytest.fixture
def sample_agent(sample_user_id: str) -> Agent:
    return Agent(
        user_id=sample_user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.",
            content=[],
        ),
        version="1.0.0",
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        action_packages=[
            ActionPackage(
                name="test-action-package",
                organization="test-organization",
                version="1.0.0",
                url="https://api.test.com",
                api_key=SecretString("test"),
                allowed_actions=["action_1", "action_2"],
            ),
            ActionPackage(
                name="test-action-package-2",
                organization="test-organization-2",
                version="1.0.0",
                url="https://api.test-2.com",
                api_key=SecretString("test-2"),
                allowed_actions=[],
            ),
        ],
        agent_architecture=AgentArchitecture(
            name="agent-architecture-default-v2",
            version="1.0.0",
        ),
        question_groups=[
            QuestionGroup(
                title="Test Question Group",
                questions=[
                    "Here's one question",
                    "Here's another question",
                ],
            ),
        ],
        observability_configs=[
            ObservabilityConfig(
                type="langsmith",
                api_key="test",
                api_url="https://api.langsmith.com",
                settings={"some_extra_setting": "some_extra_value"},
            ),
        ],
        platform_configs=[],
        extra={"agent_extra": "some_extra_value"},
    )


@pytest.fixture
def sample_thread(
    sample_user_id: str,
    sample_agent: Agent,
) -> Thread:
    return Thread(
        thread_id=str(uuid4()),
        user_id=sample_user_id,
        agent_id=sample_agent.agent_id,
        name="Test Thread",
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello, how are you?")],
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="I'm fine, thank you!")],
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"thread_metadata": "some_metadata"},
    )
