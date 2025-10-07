"""Unhandled integration settings for unknown integration kinds."""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.integrations.settings.base import IntegrationSettings


@dataclass(frozen=True)
class UnhandledIntegrationSettings(IntegrationSettings):
    """Settings for unknown integration kinds that can round-trip data."""

    kind: str
    raw_data: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        """Convert settings to dictionary by returning the raw data."""
        return self.raw_data.copy()

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "UnhandledIntegrationSettings":
        """Create settings from dictionary."""
        return cls(kind="unknown", raw_data=data.copy())
