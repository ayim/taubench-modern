from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.payloads.observability import (
    ObservabilityIntegrationResponse,
    ObservabilityIntegrationUpsertRequest,
    ObservabilitySettings,
    ObservabilityValidateOverride,
    ObservabilityValidateResponse,
)
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter(prefix="/observability", tags=["observability-integrations"])


def _integration_to_observability(integration: Integration) -> ObservabilityIntegrationResponse:
    """Convert a stored Integration into its public observability representation."""
    integration_settings = integration.settings
    if not isinstance(integration_settings, ObservabilityIntegrationSettings):
        raise ValueError("Unexpected integration settings for observability integration.")
    settings = integration_settings.settings
    # Instantiate a new ObservabilitySettings object, with a redacted secret.
    public_settings = ObservabilitySettings.model_validate(settings.model_dump(redact_secret=True))
    return ObservabilityIntegrationResponse(
        id=integration.id,
        settings=public_settings,
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
    settings = ObservabilityIntegrationSettings.from_observability_settings(payload.settings)
    integration = Integration(
        id=str(uuid4()),
        kind="observability",
        description=payload.description,
        version=payload.version,
        settings=settings,
    )
    await storage.upsert_integration(integration)
    created = await storage.get_integration(integration.id)
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
        next_settings = payload.settings
    else:
        next_settings = current_settings

    updated_integration = Integration(
        id=integration.id,
        kind="observability",
        description=(
            payload.description if payload.description is not None else integration.description
        ),
        version=payload.version if payload.version is not None else integration.version,
        settings=ObservabilityIntegrationSettings.from_observability_settings(next_settings),
        created_at=integration.created_at,
    )

    await storage.upsert_integration(updated_integration)
    refreshed = await storage.get_integration(integration_id)
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
            "kind": public_integration.settings.kind,
            "override": override.model_dump() if override else None,
        },
    )
    return response
