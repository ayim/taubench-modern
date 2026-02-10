from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.errors.responses import ErrorCode, ErrorResponse
from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.payloads import DocumentIntelligenceConfigPayload
from agent_platform.core.utils import SecretString
from agent_platform.server.api.dependencies import (
    DocIntDatasourceDependency,
    StorageDependency,
)

# Sub-routers
from agent_platform.server.api.private_v2.document_intelligence.data_models import (
    router as data_models_router,
)
from agent_platform.server.api.private_v2.document_intelligence.documents import (
    router as documents_router,
)
from agent_platform.server.api.private_v2.document_intelligence.jobs import (
    router as jobs_router,
)
from agent_platform.server.api.private_v2.document_intelligence.layouts import (
    router as layouts_router,
)
from agent_platform.server.api.private_v2.document_intelligence.quality_checks import (
    router as quality_checks_router,
)
from agent_platform.server.storage.errors import (
    IntegrationNotFoundError,
)

logger: BoundLogger = get_logger(__name__)


class DocumentIntelligenceConfigStatus(str, Enum):
    """Status values for Document Intelligence configuration responses."""

    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    NOT_AVAILABLE = "not_available"
    ERROR = "error"


@dataclass
class DocumentIntelligenceConfigResponse:
    """Response model for Document Intelligence configuration endpoints."""

    status: DocumentIntelligenceConfigStatus
    error: dict[str, Any] | None
    configuration: DocumentIntelligenceConfigPayload | None


async def _get_document_intelligence_config_response(
    storage: StorageDependency,
) -> DocumentIntelligenceConfigResponse:
    """
    Helper method to get document intelligence configuration and return it in the
    standard response format.

    This method swallows exceptions and remaps them to a 200 OK response body
    with the appropriate status, instead of raising an HTTP error.

    Returns:
        DocumentIntelligenceConfigResponse: Response with status, error, and configuration
    """
    try:
        # Get all integrations from the v2_integration table
        all_integrations = await storage.list_integrations()

        # Filter to only Reducto integrations
        reducto_integrations = [i for i in all_integrations if i.kind == IntegrationKind.REDUCTO]

        if not reducto_integrations:
            error_response = ErrorResponse(
                ErrorCode.NOT_FOUND,
                message_override="Document Intelligence configuration not found",
            )
            return DocumentIntelligenceConfigResponse(
                status=DocumentIntelligenceConfigStatus.NOT_CONFIGURED,
                error=error_response.model_dump(),
                configuration=None,
            )

        # Create and return the configuration payload
        configuration = DocumentIntelligenceConfigPayload.from_storage(
            integrations=reducto_integrations,
        )

        return DocumentIntelligenceConfigResponse(
            status=DocumentIntelligenceConfigStatus.CONFIGURED,
            error=None,
            configuration=configuration,
        )
    except IntegrationNotFoundError:
        error_response = ErrorResponse(
            ErrorCode.NOT_FOUND, message_override="Document Intelligence configuration not found"
        )
        return DocumentIntelligenceConfigResponse(
            status=DocumentIntelligenceConfigStatus.NOT_CONFIGURED,
            error=error_response.model_dump(),
            configuration=None,
        )
    except Exception:
        error_response = ErrorResponse(
            ErrorCode.UNEXPECTED,
            message_override="Document Intelligence is not available",
        )
        return DocumentIntelligenceConfigResponse(
            status=DocumentIntelligenceConfigStatus.NOT_AVAILABLE,
            error=error_response.model_dump(),
            configuration=None,
        )


router = APIRouter()


@router.get("/ok")
async def ok(docint_ds: DocIntDatasourceDependency):
    return {"ok": True}


@router.get("")
async def get_document_intelligence_config(
    storage: StorageDependency,
) -> DocumentIntelligenceConfigResponse:
    """Get Document Intelligence configuration.

    Returns the current Document Intelligence configuration including
    Reducto integration details.
    Always returns 200 OK with status indicating configuration state.
    """
    return await _get_document_intelligence_config_response(storage)


@router.post("")
async def upsert_document_intelligence(
    payload: DocumentIntelligenceConfigPayload,
    storage: StorageDependency,
) -> DocumentIntelligenceConfigResponse:
    """Upsert Document Intelligence configuration (PUT semantics).

    Accepts a configuration payload with Reducto integration details.
    Stores the integration using the v2_integration table.

    Returns the updated configuration in the same format as the GET endpoint.
    """
    # Upsert Reducto integrations
    for integration_input in payload.integrations:
        # Extract the actual API key value from SecretString if needed
        api_key_value = (
            integration_input.api_key.get_secret_value()
            if isinstance(integration_input.api_key, SecretString)
            else integration_input.api_key
        )

        reducto_settings = ReductoSettings(
            endpoint=integration_input.endpoint,
            api_key=api_key_value,
            external_id=integration_input.external_id,
        )

        integration_kind = str(integration_input.type)
        try:
            existing_integration = await storage.get_integration_by_kind(integration_kind)
            integration_id = existing_integration.id
        except IntegrationNotFoundError:
            integration_id = str(uuid4())

        doc_int_integration = Integration(
            id=integration_id,
            kind=integration_kind,
            settings=reducto_settings,
        )
        await storage.upsert_integration(doc_int_integration)

    return await _get_document_intelligence_config_response(storage)


@router.delete("")
async def clear_document_intelligence(
    storage: StorageDependency,
):
    """Clear the Document Intelligence configuration."""
    # Clear only reducto integrations (document intelligence specific)
    try:
        await storage.delete_integration(IntegrationKind.REDUCTO)
    except IntegrationNotFoundError:
        pass

    return {"ok": True}


# Sub-routers wiring
router.include_router(data_models_router)
router.include_router(quality_checks_router)
router.include_router(layouts_router)
router.include_router(documents_router)
router.include_router(jobs_router)
