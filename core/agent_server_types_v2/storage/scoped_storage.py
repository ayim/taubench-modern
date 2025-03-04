from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Literal
from uuid import UUID, uuid5

from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass
class ScopedStorage:
    """Represents a scoped storage record for storing JSON data
    tied to a particular scope."""

    STORAGE_ID_NAMESPACE: ClassVar[UUID] = UUID("13d3f0af-f771-4fb5-800a-5a7806d52a80")
    """The namespace for the storage ID generator"""

    storage_id: str = field(metadata={"description": "The ID of the storage record"})
    """The ID of the storage record"""

    created_by_user_id: str = field(
        metadata={"description": "The ID of the user who created this record"},
    )
    """The ID of the user who created this record"""

    created_by_agent_id: str = field(
        metadata={"description": "The ID of the agent who created this record"},
    )
    """The ID of the agent who created this record"""

    created_by_thread_id: str = field(
        metadata={"description": "The ID of the thread that created this record"},
    )
    """The ID of the thread that created this record"""

    scope_type: Literal["user", "agent", "thread", "global"] = field(
        metadata={
            "description": "The scope type (e.g., 'user', 'agent', 'thread', 'global')",
        },
    )
    """The scope type (e.g., 'user', 'agent', 'thread', 'global')"""

    created_at: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The timestamp when the storage record was created"},
    )
    """The timestamp when the storage record was created"""

    updated_at: datetime = field(
        default_factory=datetime.now,
        metadata={
            "description": "The timestamp when the storage record was last updated",
        },
    )
    """The timestamp when the storage record was last updated"""

    storage: Any = field(
        default_factory=dict,
        metadata={"description": "The JSON data stored for the given scope"},
    )
    """The JSON data stored for the given scope"""

    def __post_init__(self) -> None:
        assert_literal_value_valid(self, "scope_type")

    def to_json_dict(self) -> dict:
        return {
            "storage_id": self.storage_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by_user_id": self.created_by_user_id,
            "created_by_agent_id": self.created_by_agent_id,
            "created_by_thread_id": self.created_by_thread_id,
            "scope_type": self.scope_type,
            "storage": self.storage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScopedStorage":
        data = data.copy()
        for field_name in ["created_at", "updated_at"]:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        if "storage_id" in data and isinstance(data["storage_id"], UUID):
            data["storage_id"] = str(data["storage_id"])
        if (
            "created_by_user_id" in data
            and isinstance(data["created_by_user_id"], UUID)
        ):
            data["created_by_user_id"] = str(data["created_by_user_id"])
        if (
            "created_by_agent_id" in data
            and isinstance(data["created_by_agent_id"], UUID)
        ):
            data["created_by_agent_id"] = str(data["created_by_agent_id"])
        if (
            "created_by_thread_id" in data
            and isinstance(data["created_by_thread_id"], UUID)
        ):
            data["created_by_thread_id"] = str(data["created_by_thread_id"])
        return cls(**data)

    @classmethod
    def from_scope_field_value(
        cls,
        scope: Literal["user", "agent", "thread"],
        field_name: str,
        created_by_user_id: str,
        created_by_agent_id: str,
        created_by_thread_id: str,
    ) -> "ScopedStorage":
        storage_id = str(uuid5(cls.STORAGE_ID_NAMESPACE, ".".join([
            scope,
            field_name,
            created_by_user_id,
            created_by_agent_id,
            created_by_thread_id,
        ])))

        return cls(
            storage_id=storage_id,
            scope_type=scope,
            created_by_user_id=created_by_user_id,
            created_by_agent_id=created_by_agent_id,
            created_by_thread_id=created_by_thread_id,
            storage={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
