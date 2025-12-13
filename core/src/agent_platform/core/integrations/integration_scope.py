"""Integration scope data model for scoped observability configuration."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from agent_platform.core.utils.dataclass_meta import TolerantDataclass


@dataclass(frozen=True)
class IntegrationScope(TolerantDataclass):
    """Represents a scope assignment for an integration.

    Scopes determine which agents can use an integration:
    - 'global': Available to all agents in this AgentServer
    - 'agent': Available only to a specific agent (agent_id must be set)

    The design is additive: agents receive global configs + their agent-specific configs.
    """

    integration_id: str = field(
        metadata={"description": "The ID of the integration being scoped"},
    )
    """The ID of the integration being scoped"""

    agent_id: str | None = field(
        metadata={"description": "The agent ID for agent scope, None for global scope"},
    )
    """The agent ID for agent scope, None for global scope"""

    scope: Literal["global", "agent"] = field(
        metadata={"description": "The scope type: 'global' or 'agent'"},
    )
    """The scope type"""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "Timestamp when the scope assignment was created"},
    )
    """Timestamp when the scope assignment was created"""

    def model_dump(self) -> dict:
        """Convert to dictionary for serialization."""
        created_at_str = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        return {
            "integration_id": self.integration_id,
            "agent_id": self.agent_id,
            "scope": self.scope,
            "created_at": created_at_str,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "IntegrationScope":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(UTC)

        return cls(
            integration_id=data["integration_id"],
            agent_id=data.get("agent_id"),
            scope=data["scope"],
            created_at=created_at,
        )
