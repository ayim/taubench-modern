"""REST API models for observability integrations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    description: str | None = field(default=None, metadata={"description": "Optional description for the integration."})
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

    settings: ObservabilitySettingsREST | None = field(default=None, metadata={"description": "Provider settings."})
    version: str | None = field(
        default=None,
        metadata={"description": "Optional version of the integration."},
    )
    description: str | None = field(default=None, metadata={"description": "Optional description for the integration."})


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


# =============================================================================
# Integration Scope Models (REST)
# =============================================================================


class IntegrationScopeResponse(BaseModel):
    """REST response model for integration scope assignment."""

    model_config = {"frozen": True}

    integration_id: str = Field(description="ID of the integration")
    agent_id: str | None = Field(default=None, description="Agent ID if scope='agent', None if scope='global'")
    scope: Literal["global", "agent"] = Field(description="Scope type")
    created_at: datetime = Field(description="Timestamp when scope was created")


class IntegrationScopeAssignRequest(BaseModel):
    """REST request model for assigning an integration to a scope."""

    model_config = {"frozen": True}

    scope: Literal["global", "agent"] = Field(description="Scope type: 'global' or 'agent'")
    agent_id: str | None = Field(
        default=None,
        description="Agent ID (required if scope='agent', must be None if scope='global')",
    )

    @field_validator("agent_id", mode="before")
    @classmethod
    def normalize_empty_string(cls, v: str | None) -> str | None:
        """Normalize empty string to None."""
        return None if v == "" else v

    @model_validator(mode="after")
    def validate_scope_agent_relationship(self) -> "IntegrationScopeAssignRequest":
        """Validate that scope and agent_id are consistent."""
        if self.scope == "global" and self.agent_id is not None:
            raise ValueError("global scope must have agent_id=None")
        if self.scope == "agent" and self.agent_id is None:
            raise ValueError("agent scope requires agent_id")
        return self


class IntegrationScopeDeleteRequest(BaseModel):
    """Query parameters for deleting an integration scope."""

    model_config = {"frozen": True}

    scope: Literal["global", "agent"] = Field(description="Scope type: 'global' or 'agent'")
    agent_id: str | None = Field(
        default=None,
        description="Agent ID (required if scope='agent', must be None if scope='global')",
    )

    @field_validator("agent_id", mode="before")
    @classmethod
    def normalize_empty_string(cls, v: str | None) -> str | None:
        """Normalize empty string to None."""
        return None if v == "" else v

    @model_validator(mode="after")
    def validate_scope_agent_relationship(self) -> "IntegrationScopeDeleteRequest":
        """Validate that scope and agent_id are consistent."""
        if self.scope == "global" and self.agent_id is not None:
            raise ValueError("global scope must have agent_id=None")
        if self.scope == "agent" and self.agent_id is None:
            raise ValueError("agent scope requires agent_id")
        return self


__all__ = (
    "GrafanaSettingsREST",
    "IntegrationScopeAssignRequest",
    "IntegrationScopeDeleteRequest",
    "IntegrationScopeResponse",
    "LangSmithSettingsREST",
    "ObservabilityIntegrationResponse",
    "ObservabilityIntegrationUpsertRequest",
    "ObservabilitySettingsREST",
    "ObservabilityValidateOverride",
    "ObservabilityValidateResponse",
)
