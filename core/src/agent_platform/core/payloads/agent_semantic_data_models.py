"""Payload types for agent semantic data models API endpoints."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetAgentSemanticDataModelsPayload:
    """Payload for setting agent semantic data models."""

    semantic_data_model_ids: list[str] = field(
        metadata={"description": "List of semantic data model IDs to associate with the agent."},
        default_factory=list,
    )
    """List of semantic data model IDs to associate with the agent."""

    @classmethod
    def model_validate(cls, data: Any) -> "SetAgentSemanticDataModelsPayload":
        """Validate and create payload from dict data."""
        return SetAgentSemanticDataModelsPayload(
            semantic_data_model_ids=data.get("semantic_data_model_ids", []),
        )
