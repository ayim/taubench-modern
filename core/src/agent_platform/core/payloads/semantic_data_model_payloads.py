"""Payload types for semantic data model API endpoints."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetSemanticDataModelPayload:
    """Payload for setting a semantic data model."""

    semantic_model: dict = field(
        metadata={"description": "The semantic data model as a dictionary."},
    )
    """The semantic data model as a dictionary."""

    @classmethod
    def model_validate(cls, data: Any) -> "SetSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return SetSemanticDataModelPayload(
            semantic_model=data.get("semantic_model", {}),
        )


@dataclass(frozen=True)
class GetSemanticDataModelPayload:
    """Payload for getting a semantic data model."""

    semantic_data_model_id: str = field(
        metadata={"description": "The ID of the semantic data model to get."},
    )
    """The ID of the semantic data model to get."""

    @classmethod
    def model_validate(cls, data: Any) -> "GetSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return GetSemanticDataModelPayload(
            semantic_data_model_id=data["semantic_data_model_id"],
        )


@dataclass(frozen=True)
class DeleteSemanticDataModelPayload:
    """Payload for deleting a semantic data model."""

    semantic_data_model_id: str = field(
        metadata={"description": "The ID of the semantic data model to delete."},
    )
    """The ID of the semantic data model to delete."""

    @classmethod
    def model_validate(cls, data: Any) -> "DeleteSemanticDataModelPayload":
        """Validate and create payload from dict data."""
        return DeleteSemanticDataModelPayload(
            semantic_data_model_id=data["semantic_data_model_id"],
        )
