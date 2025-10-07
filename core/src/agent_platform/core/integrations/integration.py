"""Integration data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent_platform.core.integrations.settings.base import IntegrationSettings
from agent_platform.core.integrations.settings.factory import IntegrationSettingsFactory
from agent_platform.core.utils.dataclass_meta import TolerantDataclass


@dataclass(frozen=True)
class Integration(TolerantDataclass):
    """Represents a unified integration configuration."""

    id: str = field(
        metadata={
            "description": "The unique identifier for the integration",
        },
    )
    """The unique identifier for the integration"""

    kind: str = field(
        metadata={
            "description": "The type of integration (e.g., 'data_server', 'reducto')",
        },
    )
    """The type of integration"""

    settings: IntegrationSettings = field(
        metadata={
            "description": "The integration-specific settings object",
        },
    )
    """The integration-specific settings"""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(),
        metadata={
            "description": "Timestamp when the integration was created",
        },
    )
    """Timestamp when the integration was created"""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(),
        metadata={
            "description": "Timestamp when the integration was last updated",
        },
    )
    """Timestamp when the integration was last updated"""

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        """Convert the integration to a dictionary."""
        result = {
            "id": self.id,
            "kind": self.kind,
            "settings": self.settings.model_dump(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        if mode == "json":
            # Convert datetime objects to ISO format strings
            result["created_at"] = self.created_at.isoformat()
            result["updated_at"] = self.updated_at.isoformat()

        return result

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "Integration":
        """Create an Integration from a dictionary."""
        # Handle datetime conversion if needed
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif created_at is None:
            created_at = datetime.now()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        elif updated_at is None:
            updated_at = datetime.now()

        # Create settings object based on kind
        settings = IntegrationSettingsFactory.create_settings(data["kind"], data["settings"])

        return cls(
            id=data["id"],
            kind=data["kind"],
            settings=settings,
            created_at=created_at,
            updated_at=updated_at,
        )
