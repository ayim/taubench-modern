import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.runbook import Runbook, RunbookTextContent
from agent_platform.core.runbook.content import AnyRunbookContent
from agent_platform.core.utils import SecretString
from agent_platform.server.api.private_v2.compatibility.agent_compat import (
    ActionPackageCompat,
    AgentCompat,
)


@pytest.fixture
def sample_agent():
    runbook_content = cast(list[AnyRunbookContent], [RunbookTextContent(content="Sensitive runbook content")])
    runbook = Runbook(raw_text="Sensitive runbook text", content=runbook_content)
    platform_config = OpenAIPlatformParameters(
        openai_api_key=SecretString("sk-test-secret-api-key-12345"),
        platform_id=str(uuid.uuid4()),
    )
    action_package = ActionPackage(
        name="TestAP",
        organization="TestOrg",
        version="1.0.0",
        url="https://example.com",
        api_key=SecretString("ap-key-123"),
        allowed_actions=["run", "stop"],
    )
    obs_config = ObservabilityConfig(
        type="langsmith",
        api_key="obs-key-123",
        api_url="https://obs.example.com",
        settings={"project_name": "proj"},
    )
    agent = Agent(
        agent_id="agent-1",
        user_id="user-1",
        name="Agent1",
        description="desc",
        runbook_structured=runbook,
        version="1.0.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        platform_configs=[platform_config],
        action_packages=[action_package],
        mcp_servers=[],
        agent_architecture=AgentArchitecture(name="default", version="1.0.0"),
        question_groups=[],
        observability_configs=[obs_config],
        extra={},
        mode="conversational",
    )
    return agent


def test_masking_default(sample_agent):
    compat = AgentCompat.from_agent(sample_agent)
    # Platform config API key masked
    assert compat.model["config"]["openai_api_key"] == "**********"
    # Runbook text masked
    assert compat.runbook == "**********"
    # Runbook structured masked
    assert compat.runbook_structured.raw_text == "**********"
    assert compat.runbook_structured.content == []
    # Action package API key masked
    assert isinstance(compat.action_packages[0], ActionPackageCompat)
    assert compat.action_packages[0].api_key == "**********"
    # Observability config API key masked
    assert compat.advanced_config["langsmith"]["api_key"] == "**********"


def test_masking_explicit_false(sample_agent):
    compat = AgentCompat.from_agent(sample_agent, reveal_sensitive=False)
    # Platform config API key masked
    assert compat.model["config"]["openai_api_key"] == "**********"
    # Runbook text masked
    assert compat.runbook == "**********"
    # Runbook structured masked
    assert compat.runbook_structured.raw_text == "**********"
    assert compat.runbook_structured.content == []
    # Action package API key masked
    assert compat.action_packages[0].api_key == "**********"
    # Observability config API key masked
    assert compat.advanced_config["langsmith"]["api_key"] == "**********"


def test_unmasking_explicit_true(sample_agent):
    compat = AgentCompat.from_agent(sample_agent, reveal_sensitive=True)
    # Platform config API key revealed
    assert compat.model["config"]["openai_api_key"] == "sk-test-secret-api-key-12345"
    # Runbook text revealed
    assert compat.runbook == "Sensitive runbook text"
    # Runbook structured revealed
    assert compat.runbook_structured.raw_text == "Sensitive runbook text"
    assert len(compat.runbook_structured.content) == 1
    assert getattr(compat.runbook_structured.content[0], "content", None) == "Sensitive runbook content"
    # Action package API key revealed
    assert compat.action_packages[0].api_key == "ap-key-123"
    # Observability config API key revealed
    assert compat.advanced_config["langsmith"]["api_key"] == "obs-key-123"
