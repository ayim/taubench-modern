from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent


def filter_hidden_agents(agents: list["Agent"]) -> list["Agent"]:
    """Filter out agents marked as hidden in metadata."""

    return [
        agent for agent in agents if agent.extra.get("metadata", {}).get("visibility") != "hidden"
    ]
