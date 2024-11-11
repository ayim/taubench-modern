from datetime import datetime

import pytest
from pydantic import SecretStr

from agent_server_types.agents import (
    Agent,
    AgentAdvancedConfig,
    AgentMetadata,
    AgentMode,
)
from agent_server_types.constants import DEFAULT_ARCHITECTURE, RAW_CONTEXT
from agent_server_types.models import dummy_model


@pytest.fixture
def agent():
    return Agent(
        id="test_id",
        user_id="user_id",
        public=False,
        name="Test Agent",
        description="A test agent",
        runbook=SecretStr("This is a secret runbook"),
        version="1.0",
        model=dummy_model,
        advanced_config=AgentAdvancedConfig(
            architecture=DEFAULT_ARCHITECTURE, reasoning="disabled"
        ),
        action_packages=[],
        updated_at=datetime.now(),
        created_at=datetime.now(),
        metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
    )


def test_agent_serialization_masked(agent: Agent):
    serialized = agent.model_dump()
    assert str(serialized["runbook"]) == "**********"


def test_agent_serialization_raw(agent: Agent):
    serialized = agent.model_dump(context=RAW_CONTEXT)
    assert serialized["runbook"] == "This is a secret runbook"
