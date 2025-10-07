"""Reducto integration settings."""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.integrations.settings.base import IntegrationSettings
from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class ReductoSettings(IntegrationSettings):
    """Settings for Reducto integration."""

    endpoint: str
    api_key: str | SecretString
    external_id: str | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        result = {
            "endpoint": self.endpoint,
            "api_key": self.api_key,
        }
        if self.external_id:
            result["external_id"] = self.external_id
        return result

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "ReductoSettings":
        """Create settings from dictionary."""
        return cls(
            endpoint=data["endpoint"],
            api_key=data["api_key"],
            external_id=data.get("external_id"),
        )
