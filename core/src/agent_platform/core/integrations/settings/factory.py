"""Factory for creating integration settings objects."""

from typing import Any, ClassVar

from agent_platform.core.integrations.settings.base import IntegrationSettings
from agent_platform.core.integrations.settings.data_server import DataServerSettings
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.integrations.settings.unhandled import UnhandledIntegrationSettings


class IntegrationSettingsFactory:
    """Factory for creating integration settings objects."""

    _settings_classes: ClassVar[dict[str, type[IntegrationSettings]]] = {
        "data_server": DataServerSettings,
        "observability": ObservabilityIntegrationSettings,
        "reducto": ReductoSettings,
    }

    @classmethod
    def create_settings(cls, kind: str, data: dict[str, Any]) -> IntegrationSettings:
        """Create settings object based on integration kind."""
        settings_class = cls._settings_classes.get(kind)
        if not settings_class:
            return UnhandledIntegrationSettings(kind=kind, raw_data=data)

        return settings_class.model_validate(data)
