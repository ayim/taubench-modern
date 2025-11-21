"""REST API models for observability integrations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# REST API Models
# =============================================================================


class GrafanaSettingsREST(BaseModel):
    """Grafana observability settings for REST API."""

    model_config = ConfigDict(frozen=True)

    provider: Literal["grafana"] = "grafana"
    url: str = Field(description="Full OTLP traces endpoint")
    api_token: str = Field(description="Grafana API token")
    grafana_instance_id: str = Field(description="Grafana instance ID")
    additional_headers: dict[str, str] | None = Field(
        default=None,
        description="Optional HTTP headers to send with the request to Grafana Cloud.",
    )
    is_enabled: bool = True


class LangSmithSettingsREST(BaseModel):
    """LangSmith observability settings for REST API."""

    model_config = ConfigDict(frozen=True)

    provider: Literal["langsmith"] = "langsmith"
    url: str = Field(description="LangSmith OTLP endpoint")
    project_name: str = Field(description="LangSmith project name")
    api_key: str = Field(description="LangSmith API key")
    is_enabled: bool = True


ObservabilitySettingsREST = Annotated[
    GrafanaSettingsREST | LangSmithSettingsREST,
    Field(discriminator="provider"),
]


# =============================================================================
# REST Request/Response Wrappers
# =============================================================================


@dataclass(frozen=True)
class ObservabilityIntegrationResponse:
    """Response representation of a stored observability integration."""

    id: str = field(metadata={"description": "The UUID of the integration."})
    settings: ObservabilitySettingsREST = field(metadata={"description": "Provider settings."})
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
    """Payload for creating/updating an observability integration."""

    settings: ObservabilitySettingsREST | None = field(
        default=None, metadata={"description": "Provider settings."}
    )
    version: str | None = field(
        default=None,
        metadata={"description": "Optional version of the integration."},
    )
    description: str | None = field(
        default=None, metadata={"description": "Optional description for the integration."}
    )


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
    "GrafanaSettingsREST",
    "LangSmithSettingsREST",
    "ObservabilityIntegrationResponse",
    "ObservabilityIntegrationUpsertRequest",
    "ObservabilitySettingsREST",
    "ObservabilityValidateOverride",
    "ObservabilityValidateResponse",
)
