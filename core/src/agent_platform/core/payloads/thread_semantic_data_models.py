"""Payload types for thread semantic data models API endpoints."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetThreadSemanticDataModelsPayload:
    """Payload for setting thread semantic data models."""

    semantic_data_model_ids: list[str] = field(
        metadata={"description": "List of semantic data model IDs to associate with the thread."},
        default_factory=list,
    )
    """List of semantic data model IDs to associate with the thread."""

    @classmethod
    def model_validate(cls, data: Any) -> "SetThreadSemanticDataModelsPayload":
        """Validate and create payload from dict data."""
        return SetThreadSemanticDataModelsPayload(
            semantic_data_model_ids=data.get("semantic_data_model_ids", []),
        )
