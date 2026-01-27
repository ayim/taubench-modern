from importlib.metadata import entry_points

import pytest

from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.runbook import Runbook
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat


def _make_minimal_agent(arch_name: str) -> Agent:
    """Create a minimal Agent instance for compatibility testing."""
    return Agent(
        name="CompatAgent",
        description="desc",
        user_id="user-1",
        runbook_structured=Runbook(raw_text="Hello", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name=arch_name, version="1.0.0"),
        action_packages=[],
        mcp_servers=[],
        mcp_server_ids=[],
        platform_params_ids=[],
        question_groups=[],
        observability_configs=[],
        extra={},
        mode="conversational",
    )


@pytest.mark.unit
def test_all_entrypoint_architectures_map_to_agent_or_self():
    """Every installed architecture name maps to 'agent' or its own name.

    - Default architecture must map to 'agent'.
    - Experimental architectures map to their own name.
    """
    eps = entry_points(group="agent_platform.architectures")
    assert eps, "Expected at least one architecture entrypoint to be installed"

    for ep in eps:
        agent = _make_minimal_agent(ep.name)
        compat = AgentCompat.from_agent(agent)
        arch_value = compat.advanced_config.get("architecture")

        # Default must map to 'agent'
        if ep.name == "agent_platform.architectures.default":
            assert arch_value == "agent"
            continue

        # Otherwise, it should be 'agent' or its own name (experimental variants)
        if "experimental" in ep.name:
            assert arch_value == ep.name
        else:
            assert arch_value == "agent"


@pytest.mark.unit
def test_unknown_non_experimental_architecture_maps_to_agent():
    """Garbage/unknown non-experimental architecture names map to 'agent'."""
    unknown_name = "agent_platform.architectures.unknown_architecture_v1"
    agent = _make_minimal_agent(unknown_name)
    compat = AgentCompat.from_agent(agent)
    assert compat.advanced_config.get("architecture") == "agent"


@pytest.mark.unit
def test_unknown_experimental_architecture_maps_to_self():
    """Unknown experimental names continue to map to their own name."""
    unknown_exp_name = "agent_platform.architectures.experimental_9999"
    agent = _make_minimal_agent(unknown_exp_name)
    compat = AgentCompat.from_agent(agent)
    assert compat.advanced_config.get("architecture") == unknown_exp_name
