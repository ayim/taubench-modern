"""Observability integration settings."""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.integrations.observability.models import ObservabilitySettings
from agent_platform.core.integrations.settings.base import IntegrationSettings


@dataclass(frozen=True, init=False)
class ObservabilityIntegrationSettings(IntegrationSettings):
    """Integration settings wrapper for observability providers."""

    settings: ObservabilitySettings

    def __init__(self, settings: ObservabilitySettings):
        object.__setattr__(self, "settings", settings)

    @classmethod
    def from_observability_settings(
        cls,
        settings: ObservabilitySettings,
    ) -> "ObservabilityIntegrationSettings":
        return cls(settings)

    @property
    def provider_kind(self) -> str:
        return self.settings.kind

    @property
    def is_enabled(self) -> bool:
        return self.settings.is_enabled

    @property
    def provider_settings(self):
        return self.settings.provider_settings

    def model_dump(self) -> dict[str, Any]:
        """Serialize settings for storage (secrets preserved)."""
        return self.settings.model_dump(redact_secret=False)

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "ObservabilityIntegrationSettings":
        """Deserialize settings from storage."""
        settings = ObservabilitySettings.model_validate(data)
        return cls(settings)
