from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class AgentPackageCreatePayload:
    agent_id: str = field(
        metadata={
            "description": ("The ID of the agent to create the agent package from."),
        },
    )
    """The ID of the agent to create the agent package from."""

    action_packages_uris: list[str] = field(
        metadata={
            "description": ("The URIs of the action packages to include in the agent package."),
        },
    )
    """The URIs of the action packages to include in the agent package."""

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        if isinstance(data, cls):
            return data

        agent_id = data.get("agent_id", "")
        action_packages_uris = data.get("action_packages_uris", [])

        if not agent_id:
            raise ValueError("Agent ID is required")

        return cls(agent_id=agent_id, action_packages_uris=action_packages_uris)
