"""REST API endpoints for observability integrations."""

from datetime import UTC
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import TypeAdapter

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.integrations import Integration, IntegrationScope
from agent_platform.core.integrations.observability.models import (
    GrafanaObservabilitySettings,
    LangSmithObservabilitySettings,
    ObservabilitySettings,
    OtlpBasicAuthObservabilitySettings,
    OtlpCustomHeadersObservabilitySettings,
)
from agent_platform.core.integrations.settings.observability import (
    ObservabilityIntegrationSettings,
)
from agent_platform.core.telemetry.otel_orchestrator import OtelOrchestrator
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

from .models import (
    IntegrationScopeAssignRequest,
    IntegrationScopeDeleteRequest,
    IntegrationScopeResponse,
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
    elif rest_settings.provider == "otlp_basic_auth":
        return ObservabilitySettings(
            kind="otlp_basic_auth",
            provider_settings=OtlpBasicAuthObservabilitySettings(
                url=rest_settings.url,
                username=rest_settings.username,
                password=SecretString(rest_settings.password),
            ),
            is_enabled=rest_settings.is_enabled,
        )
    elif rest_settings.provider == "otlp_custom_headers":
        return ObservabilitySettings(
            kind="otlp_custom_headers",
            provider_settings=OtlpCustomHeadersObservabilitySettings(
                url=rest_settings.url,
                headers=rest_settings.headers,
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
    agent_id: str | None = Query(default=None),
) -> list[ObservabilityIntegrationResponse]:
    """List observability integrations.

    - If agent_id is provided: Returns all integrations applicable to that agent
      (global + agent-specific, additive model)
    - Otherwise: Returns all observability integrations, optionally filtered by provider
    """
    # If agent_id is provided, use the additive query for that agent
    if agent_id:
        # The get_agent call will raise an error if the agent does not exist.
        await storage.get_agent(user.user_id, agent_id)
        integrations = await storage.get_observability_integrations_for_agent(agent_id)
    else:
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
    """Create a new observability integration.

    If the integration is enabled, it is automatically assigned global scope
    so it starts receiving spans immediately.
    """
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
    # Storage layer auto-assigns global scope if no scopes exist
    await storage.upsert_integration(integration)

    created = await storage.get_integration(integration.id)

    # Reload orchestrator from storage
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info("Reloaded orchestrator after creating integration", integration_id=created.id)

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
        description=(payload.description if payload.description is not None else integration.description),
        version=payload.version if payload.version is not None else integration.version,
        settings=updated_settings,
        created_at=integration.created_at,
    )

    # Storage layer auto-assigns global scope if no scopes exist
    await storage.upsert_integration(updated_integration)
    refreshed = await storage.get_integration(integration_id)

    # Reload orchestrator from storage
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info("Reloaded orchestrator after updating integration", integration_id=refreshed.id)

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

    # Reload orchestrator from storage
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)
    logger.info("Reloaded orchestrator after deleting integration", integration_id=integration_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/integrations/{integration_id}/validate")
async def validate_observability_integration(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    override: ObservabilityValidateOverride | None = None,
) -> ObservabilityValidateResponse:
    """Validate an observability integration by sending a test trace."""
    from datetime import datetime

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.trace import SpanKind, Status, StatusCode

    # NOTE: get_integration returns any type of integration. Consider adding
    # a dedicated storage.get_observability_integration that returns NOT_FOUND
    # for non-observability integrations, removing the need for isinstance checks.
    integration = await storage.get_integration(integration_id)
    integration_settings = integration.settings
    if not isinstance(integration_settings, ObservabilityIntegrationSettings):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observability integration not found.",
        )

    internal_settings = integration_settings.settings
    provider_settings = internal_settings.provider_settings

    # Apply URL override if provided
    if override and override.url:
        # Create a modified copy of provider settings with overridden URL
        provider_data = provider_settings.model_dump(redact_secret=False)
        provider_data["url"] = override.url
        provider_cls = type(provider_settings)
        provider_settings = provider_cls.model_validate(provider_data)

    try:
        # Create an exporter using the provider factory
        from agent_platform.core.integrations.observability.models import ObservabilitySettings
        from agent_platform.core.telemetry.providers.factory import OtelProviderFactory

        # Wrap provider settings in ObservabilitySettings for the factory
        validation_settings = ObservabilitySettings(
            kind=internal_settings.kind,
            provider_settings=provider_settings,
        )
        provider = OtelProviderFactory.create(validation_settings)
        exporter: SpanExporter = provider._create_trace_exporter()

        # Create a test span with BatchSpanProcessor to capture it
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        resource = Resource.create(
            {
                "service.name": "agent-platform-observability-test",
                "test.validation": "true",
            }
        )
        tracer_provider = TracerProvider(resource=resource)

        # Collect spans for export
        collected_spans = []

        class CollectingSpanProcessor(SimpleSpanProcessor):
            def on_end(self, span):
                collected_spans.append(span)
                # Don't call super().on_end() to avoid automatic export

        collecting_processor = CollectingSpanProcessor(exporter)
        tracer_provider.add_span_processor(collecting_processor)

        tracer = tracer_provider.get_tracer("observability-test")

        # Create and end a test span
        with tracer.start_as_current_span(
            "observability.test.heartbeat",
            kind=SpanKind.INTERNAL,
        ) as span:
            span.set_attribute("test.type", "validation")
            span.set_attribute("test.provider", internal_settings.kind)
            span.set_attribute("test.timestamp", datetime.now(UTC).isoformat())
            span.set_attribute("test.integration_id", integration_id)
            span.set_status(Status(StatusCode.OK, "Test heartbeat successful"))

        # Now export the collected span
        if collected_spans:
            result = exporter.export(collected_spans)
        else:
            result = SpanExportResult.FAILURE

        exporter.shutdown()
        tracer_provider.shutdown()

        if result == SpanExportResult.SUCCESS:
            response = ObservabilityValidateResponse(
                success=True,
                message="Successfully sent test heartbeat to observability platform.",
                details={
                    "provider": internal_settings.kind,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        else:
            response = ObservabilityValidateResponse(
                success=False,
                message=f"Failed to export test span: {result}",
                details={
                    "provider": internal_settings.kind,
                    "export_result": str(result),
                },
            )
    except Exception as e:
        logger.exception("Error validating observability integration", integration_id=integration_id)
        response = ObservabilityValidateResponse(
            success=False,
            message=f"Validation failed: {e!s}",
            details={
                "provider": internal_settings.kind,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
    return response


# =============================================================================
# Integration Scope Endpoints
# =============================================================================


def _scope_to_response(scope: IntegrationScope) -> IntegrationScopeResponse:
    """Convert internal IntegrationScope to REST response model."""
    return IntegrationScopeResponse(
        integration_id=scope.integration_id,
        agent_id=scope.agent_id,
        scope=scope.scope,
        created_at=scope.created_at,
    )


@router.get("/integrations/{integration_id}/scopes")
async def list_integration_scopes(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> list[IntegrationScopeResponse]:
    """List all scope assignments for an integration."""
    # Verify integration exists and is observability type
    integration = await storage.get_integration(integration_id)
    if integration.kind != "observability":
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message="Observability integration not found.",
        )

    scopes = await storage.list_integration_scopes(integration_id)
    return [_scope_to_response(scope) for scope in scopes]


@router.post(
    "/integrations/{integration_id}/scopes",
    status_code=status.HTTP_201_CREATED,
)
async def set_integration_scope(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    payload: IntegrationScopeAssignRequest,
) -> IntegrationScopeResponse:
    """Set an integration scope (global or agent-specific). Idempotent."""
    # Verify integration exists and is observability type
    integration = await storage.get_integration(integration_id)
    if integration.kind != "observability":
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message="Observability integration not found.",
        )

    # Verify agent exists if agent scope is requested
    # Pydantic validation ensures agent_id is not None when scope='agent'
    if payload.scope == "agent":
        # The get_agent call will raise an error if the agent does not exist.
        await storage.get_agent(user.user_id, payload.agent_id)  # type: ignore

    scope = await storage.set_integration_scope(
        integration_id=integration_id,
        scope=payload.scope,
        agent_id=payload.agent_id,
    )

    # Reload orchestrator from storage (rebuilds routing map)
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)

    logger.info(
        "Set integration scope",
        extra={
            "integration_id": integration_id,
            "scope": scope.scope,
            "agent_id": scope.agent_id,
        },
    )

    return _scope_to_response(scope)


@router.delete(
    "/integrations/{integration_id}/scopes",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_integration_scope(
    integration_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    # Depends() tells FastAPI to construct the Pydantic model
    # from query parameters instead of expecting it as a request body.
    params: Annotated[IntegrationScopeDeleteRequest, Depends()],
) -> Response:
    """Delete a scope assignment.

    - For global scope: scope='global', agent_id=None (or omitted)
    - For agent scope: scope='agent', agent_id=<uuid>
    """
    # Pydantic validation ensures scope and agent_id are consistent
    await storage.delete_integration_scope(integration_id, params.scope, params.agent_id)

    # Reload orchestrator from storage (rebuilds routing map)
    orchestrator = OtelOrchestrator.get_instance()
    await orchestrator.reload_from_storage(storage)

    logger.info(
        "Deleted integration scope",
        extra={
            "integration_id": integration_id,
            "agent_id": params.agent_id,
            "scope": params.scope,
        },
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
