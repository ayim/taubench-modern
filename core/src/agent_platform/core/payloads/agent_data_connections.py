"""Payload types for agent data connections API endpoints."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetAgentDataConnectionsPayload:
    """Payload for setting agent data connections."""

    data_connection_ids: list[str] = field(
        metadata={"description": "List of data connection IDs to associate with the agent."},
        default_factory=list,
    )
    """List of data connection IDs to associate with the agent."""

    @classmethod
    def model_validate(cls, data: Any) -> "SetAgentDataConnectionsPayload":
        """Validate and create payload from dict data."""
        return SetAgentDataConnectionsPayload(
            data_connection_ids=data.get("data_connection_ids", []),
        )


@dataclass(frozen=True)
class GetAgentDataConnectionsPayload:
    """Payload for getting agent data connections."""

    agent_id: str = field(
        metadata={"description": "The ID of the agent to get data connections for."},
    )
    """The ID of the agent to get data connections for."""

    @classmethod
    def model_validate(cls, data: Any) -> "GetAgentDataConnectionsPayload":
        """Validate and create payload from dict data."""
        return GetAgentDataConnectionsPayload(
            agent_id=data["agent_id"],
        )
