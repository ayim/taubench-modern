from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from agent_platform.core.integrations.observability.models import ObservabilitySettings


@dataclass(frozen=True)
class ObservabilityIntegrationResponse:
    """Response representation of a stored observability integration."""

    id: str = field(metadata={"description": "The UUID of the integration."})
    settings: ObservabilitySettings = field(metadata={"description": "Provider settings."})
    created_at: datetime = field(
        metadata={"description": "Timestamp when the integration was created."},
    )
    updated_at: datetime = field(
        metadata={"description": "Timestamp when the integration was last updated."},
    )
    description: str | None = field(
        default=None, metadata={"description": "Optional description for the integration."}
    )
    version: str | None = field(
        default=None,
        metadata={"description": "Optional version of the integration."},
    )
    kind: Literal["observability"] = field(
        default="observability",
        metadata={"description": "Integration kind (always observability)."},
    )


@dataclass(frozen=True)
class ObservabilityIntegrationUpsertRequest:
    """Payload for creating a global observability integration."""

    settings: ObservabilitySettings | None = field(
        default=None, metadata={"description": "Provider settings."}
    )
    version: str | None = field(
        default=None,
        metadata={"description": "Optional version of the integration."},
    )
    description: str | None = field(
        default=None, metadata={"description": "Optional description for the integration."}
    )

    def model_dump(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.settings is not None:
            data["settings"] = self.settings.model_dump(redact_secret=True)
        if self.description is not None:
            data["description"] = self.description
        if self.version is not None:
            data["version"] = self.version
        return data


@dataclass(frozen=True)
class ObservabilityValidateOverride:
    """Optional overrides used only during validation (not persisted)."""

    url: str | None = field(
        default=None,
        metadata={"description": "Optional override for OTLP endpoint during validation."},
    )

    def model_dump(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.url is not None:
            data["url"] = self.url
        return data


@dataclass(frozen=True)
class ObservabilityValidateResponse:
    """Result of validating observability integration connectivity/auth."""

    success: bool = field(metadata={"description": "Whether validation succeeded."})
    message: str | None = field(
        default=None,
        metadata={"description": "Human-readable summary of validation outcome."},
    )
    details: dict[str, Any] | None = field(
        default=None,
        metadata={"description": "Provider-specific diagnostics (e.g., status code, latency)."},
    )

    def model_dump(self) -> dict[str, Any]:
        data: dict[str, Any] = {"success": self.success}

        if self.message is not None:
            data["message"] = self.message
        if self.details is not None:
            data["details"] = self.details

        return data


__all__ = (
    "ObservabilityIntegrationResponse",
    "ObservabilityIntegrationUpsertRequest",
    "ObservabilityValidateOverride",
    "ObservabilityValidateResponse",
)
