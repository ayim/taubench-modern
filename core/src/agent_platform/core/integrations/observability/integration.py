from dataclasses import dataclass
from typing import Any, Literal

from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)


@dataclass(frozen=True)
class ObservabilityIntegration(Integration):
    """Represents a unified observability integration configuration.

    This is a more specific implementation of Integration that enforces:
    - kind is always "observability" (Literal type)
    - settings is specifically ObservabilityIntegrationSettings (not generic IntegrationSettings)

    Note: Type narrowing is enforced through model_validate rather than field redeclaration
    to avoid dataclass field ordering issues with inheritance.
    """

    # Type annotations for narrowing
    kind: Literal["observability"]
    settings: ObservabilityIntegrationSettings

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        """Convert the observability integration to a dictionary.

        This override ensures proper serialization of ObservabilityIntegrationSettings.
        """
        # The base implementation already handles everything correctly
        return super().model_dump(mode=mode)

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "ObservabilityIntegration":
        """Create an ObservabilityIntegration from a dictionary.

        This override ensures we create ObservabilityIntegrationSettings specifically,
        rather than using the generic factory pattern.
        """
        # Validate kind is "observability"
        kind = data.get("kind", "observability")
        if kind != "observability":
            raise ValueError(f"ObservabilityIntegration requires kind='observability', got '{kind}'")

        # Create ObservabilityIntegrationSettings directly (bypassing factory)
        settings = ObservabilityIntegrationSettings.model_validate(data["settings"])

        # Delegate to parent for datetime handling and other common logic
        # by creating a base Integration first
        base_integration = super().model_validate(data)

        # Return ObservabilityIntegration with our specific settings
        # and the parent's validated datetime fields
        return cls(
            id=base_integration.id,
            settings=settings,
            kind="observability",
            description=base_integration.description,
            version=base_integration.version,
            created_at=base_integration.created_at,
            updated_at=base_integration.updated_at,
        )
