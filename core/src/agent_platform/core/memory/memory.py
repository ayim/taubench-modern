from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID


@dataclass(frozen=True)
class Memory:
    """Represents a memory in the agent's memory store."""

    memory_id: str = field(metadata={"description": "The ID of the memory"})
    """The ID of the memory"""

    original_text: str = field(
        metadata={"description": "The original text content of the memory"},
    )
    """The original text content of the memory"""

    contextualized_text: str | None = field(
        default=None,
        metadata={"description": "The contextualized text content of the memory"},
    )
    """The contextualized text content of the memory"""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp of when the memory was created"},
    )
    """The timestamp of when the memory was created"""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The timestamp of when the memory was last updated"},
    )
    """The timestamp of when the memory was last updated"""

    relevant_until_timestamp: datetime | None = field(
        default=None,
        metadata={
            "description": "The timestamp of when the memory is no longer relevant",
        },
    )
    """The timestamp of when the memory is no longer relevant"""

    relevant_after_timestamp: datetime | None = field(
        default=None,
        metadata={
            "description": "The timestamp of when the memory becomes relevant",
        },
    )
    """The timestamp of when the memory becomes relevant"""

    scope: Literal[
        "user",
        "thread",
        "tool",
        "agent",
        "architecture",
        "organization",
        "global",
    ] = field(
        default="global",
        metadata={"description": "The scope of the memory"},
    )
    """The scope of the memory"""

    metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The metadata associated with this memory"},
    )
    """The metadata associated with this memory"""

    tags: list[str] = field(
        default_factory=list,
        metadata={"description": "The tags associated with this memory"},
    )
    """The tags associated with this memory"""

    refs: list[str] = field(
        default_factory=list,
        metadata={"description": "The references associated with this memory"},
    )
    """The references associated with this memory"""

    weight: float = field(
        default=1.0,
        metadata={"description": "The weight of the memory"},
    )
    """The weight of the memory"""

    embedded: bool = field(
        default=False,
        metadata={"description": "Whether the memory is embedded"},
    )
    """Whether the memory is embedded"""

    embedding: list[float] | None = field(
        default=None,
        metadata={"description": "The embedding of the memory"},
    )
    """The embedding of the memory"""

    embedding_id: str | None = field(
        default=None,
        metadata={
            "description": "The ID of the linked embedding(possibly stored externally)",
        },
    )
    """The ID of the linked embedding (possibly stored externally)"""

    def model_dump(self) -> dict:
        """Serializes the memory entry to a dictionary.
        Useful for JSON serialization."""
        return {
            "memory_id": self.memory_id,
            "original_text": self.original_text,
            "contextualized_text": self.contextualized_text,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "relevant_until_timestamp": (
                self.relevant_until_timestamp.isoformat() if self.relevant_until_timestamp else None
            ),
            "relevant_after_timestamp": (
                self.relevant_after_timestamp.isoformat() if self.relevant_after_timestamp else None
            ),
            "scope": self.scope,
            "metadata": self.metadata,
            "tags": self.tags,
            "refs": self.refs,
            "weight": self.weight,
            "embedded": self.embedded,
            "embedding_id": self.embedding_id,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "Memory":
        """Create a memory from a dictionary."""
        data = data.copy()

        datetime_fields = [
            "created_at",
            "updated_at",
            "relevant_until_timestamp",
            "relevant_after_timestamp",
        ]
        for df_field in datetime_fields:
            if df_field in data and data[df_field] is not None:
                if isinstance(data[df_field], str):
                    data[df_field] = datetime.fromisoformat(data[df_field])
        if "memory_id" in data and isinstance(data["memory_id"], UUID):
            data["memory_id"] = str(data["memory_id"])

        return cls(**data)
