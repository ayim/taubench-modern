"""REST API endpoints for observability integrations."""

from typing import cast
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import TypeAdapter

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
)
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.otel_orchestrator import OtelOrchestrator
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

from .models import (
    ObservabilityIntegrationResponse,
    ObservabilityIntegrationUpsertRequest,
    ObservabilitySettingsREST,
    ObservabilityValidateOverride,
    ObservabilityValidateResponse,
)

router = APIRouter(prefix="/observability", tags=["observability-integrations"])

logger = structlog.get_logger(__name__)


def _rest_to_internal(rest_settings: ObservabilitySettingsREST) -> ObservabilitySettings:
    """Convert REST request model to internal dataclass model."""
    if rest_settings.provider == "grafana":
        return ObservabilitySettings(
            kind="grafana",
            provider_settings=GrafanaObservabilitySettings(
                url=rest_settings.url,
                api_token=SecretString(rest_settings.api_token),
                grafana_instance_id=rest_settings.grafana_instance_id,
                additional_headers=rest_settings.additional_headers,
            ),
            is_enabled=rest_settings.is_enabled,
        )
    elif rest_settings.provider == "langsmith":
        return ObservabilitySettings(
            kind="langsmith",
            provider_settings=LangSmithObservabilitySettings(
                url=rest_settings.url,
                project_name=rest_settings.project_name,
                api_key=SecretString(rest_settings.api_key),
            ),
            is_enabled=rest_settings.is_enabled,
        )
    else:
        raise ValueError(f"Unsupported observability provider: {rest_settings.provider}")


def _internal_to_rest(internal_settings: ObservabilitySettings) -> ObservabilitySettingsREST:
    """Convert internal dataclass model to REST response model."""
    data = internal_settings.model_dump(redact_secret=False)

    provider_settings = data.pop("provider_settings")
    flattened = {**data, **provider_settings}
    flattened["provider"] = flattened.pop("kind")

    adapter = TypeAdapter(ObservabilitySettingsREST)
    return adapter.validate_python(flattened)


def _integration_to_observability(integration: Integration) -> ObservabilityIntegrationResponse:
    """Convert a stored Integration into its public REST API representation."""
    integration_settings = integration.settings
    if not isinstance(integration_settings, ObservabilityIntegrationSettings):
        raise ValueError("Unexpected integration settings for observability integration.")

    internal_settings = integration_settings.settings
    rest_settings = _internal_to_rest(internal_settings)

    return ObservabilityIntegrationResponse(
        id=integration.id,
        settings=rest_settings,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
        description=integration.description,
        version=integration.version,
    )


@router.get("/integrations")
async def list_observability_integrations(
    user: AuthedUser,
    storage: StorageDependency,
    provider: str | None = Query(default=None),
) -> list[ObservabilityIntegrationResponse]:
    """List observability integrations, optionally filtered by provider."""
    integrations = await storage.list_integrations(kind="observability")

    response_items: list[ObservabilityIntegrationResponse] = []
    filter_flag = provider is not None
    for integration in integrations:
        if filter_flag:
            settings = integration.settings
            if not isinstance(settings, ObservabilityIntegrationSettings):
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Unexpected integration settings for observability integration.",
                )
            if settings.provider_kind != provider:
                continue
        response_items.append(_integration_to_observability(integration))
    return response_items


@router.post(
    "/integrations",
    status_code=status.HTTP_201_CREATED,
)
async def create_observability_integration(
    user: AuthedUser,
    storage: StorageDependency,
    payload: ObservabilityIntegrationUpsertRequest,
) -> ObservabilityIntegrationResponse:
    """Create a new observability integration."""
    if not payload.settings or not payload.version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Settings and version are required.",
        )

    # Convert REST settings to internal settings
    internal_settings = _rest_to_internal(payload.settings)
    settings = ObservabilityIntegrationSettings.from_observability_settings(internal_settings)

    integration = Integration(
        id=str(uuid4()),
        kind="observability",
        description=payload.description,
        version=payload.version,
        settings=settings,
    )
    await storage.upsert_integration(integration)

    created = await storage.get_integration(integration.id)
    # We are positive that we have an observability integration, cast it.
    created_obs = cast(ObservabilityIntegration, created)

    # Hot-reload in orchestrator
    orchestrator = OtelOrchestrator.get_instance()
    orchestrator.reload_integration(created_obs)
    logger.info(f"Hot-reloaded observability integration: {created.id}")

    return _integration_to_observability(created)


@router.get("/integrations/{integration_id}")
async def get_observability_integration(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> ObservabilityIntegrationResponse:
    """Get an observability integration by ID."""
    integration = await storage.get_integration(integration_id)
    # Don't want to return non-observability integrations.
    if integration.kind != "observability":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found.",
        )
    return _integration_to_observability(integration)


@router.put("/integrations/{integration_id}")
async def update_observability_integration(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    payload: ObservabilityIntegrationUpsertRequest,
) -> ObservabilityIntegrationResponse:
    """Update an observability integration."""
    integration = await storage.get_integration(integration_id)
    integration_settings = integration.settings
    if not isinstance(integration_settings, ObservabilityIntegrationSettings):
        raise ValueError("Unexpected integration settings for observability integration.")
    current_settings = integration_settings.settings

    if payload.settings:
        # Convert REST settings to internal settings
        next_settings = _rest_to_internal(payload.settings)
    else:
        next_settings = current_settings

    updated_settings = ObservabilityIntegrationSettings.from_observability_settings(next_settings)
    updated_integration = Integration(
        id=integration.id,
        kind="observability",
        description=(
            payload.description if payload.description is not None else integration.description
        ),
        version=payload.version if payload.version is not None else integration.version,
        settings=updated_settings,
        created_at=integration.created_at,
    )

    await storage.upsert_integration(updated_integration)
    refreshed = await storage.get_integration(integration_id)
    # We are positive that we have an observability integration, cast it.
    refreshed_obs = cast(ObservabilityIntegration, refreshed)

    # Hot-reload in orchestrator
    orchestrator = OtelOrchestrator.get_instance()
    orchestrator.reload_integration(refreshed_obs)
    logger.info(f"Hot-reloaded observability integration: {refreshed.id}")

    return _integration_to_observability(refreshed)


@router.delete(
    "/integrations/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_observability_integration(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> Response:
    """Delete an observability integration."""
    await storage.delete_integration_by_id(integration_id)

    # Remove from orchestrator
    orchestrator = OtelOrchestrator.get_instance()
    orchestrator.remove_integration(integration_id)
    logger.info(f"Removed observability integration from orchestrator: {integration_id}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/integrations/{integration_id}/validate")
async def validate_observability_integration(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    override: ObservabilityValidateOverride | None = None,
) -> ObservabilityValidateResponse:
    """Validate an observability integration (placeholder implementation)."""
    integration = await storage.get_integration(integration_id)
    public_integration = _integration_to_observability(integration)
    response = ObservabilityValidateResponse(
        success=False,
        message="Validation logic not implemented yet.",
        details={
            "provider": public_integration.settings.provider,
            "override": override.model_dump() if override else None,
        },
    )
    return response
