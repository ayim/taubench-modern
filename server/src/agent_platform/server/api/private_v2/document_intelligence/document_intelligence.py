from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import APIRouter
from sema4ai.data import DataSource
from sema4ai_docint.models import initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.data_server.data_sources import DataSources
from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode, ErrorResponse
from agent_platform.core.payloads import DocumentIntelligenceConfigPayload
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
from agent_platform.server.data_server.data_source import initialize_data_source
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    DocumentIntelligenceIntegrationNotFoundError,
)

logger: BoundLogger = get_logger(__name__)


class DocumentIntelligenceConfigStatus(str, Enum):
    """Status values for Document Intelligence configuration responses."""

    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    NOT_AVAILABLE = "not_available"


@dataclass
class DocumentIntelligenceConfigResponse:
    """Response model for Document Intelligence configuration endpoints."""

    status: DocumentIntelligenceConfigStatus
    error: dict[str, Any] | None
    configuration: DocumentIntelligenceConfigPayload | None


async def _build_datasource(data_sources: DataSources):
    """
    Initialize the Document Intelligence database in the Data Server.
    """
    try:
        await initialize_data_source(data_sources)

        # Also create the DocInt tables in the database.
        docint_ds = DataSource.model_validate(datasource_name=DATA_SOURCE_NAME)
        initialize_database("postgres", docint_ds)
    except Exception as e:
        raise PlatformError(
            ErrorCode.UNEXPECTED,
            f"Error initializing Document Intelligence database: Error: {e}",
        ) from e


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
        # Get data server connection details
        data_server_details = await storage.get_dids_connection_details()

        # Get all integrations
        integrations = await storage.list_document_intelligence_integrations()

        # Get data connections
        data_connections = await storage.get_dids_data_connections()

        # Create and return the configuration payload
        configuration = DocumentIntelligenceConfigPayload.from_storage(
            data_server_details=data_server_details,
            integrations=integrations,
            data_connections=data_connections,
        )

        return DocumentIntelligenceConfigResponse(
            status=DocumentIntelligenceConfigStatus.CONFIGURED,
            error=None,
            configuration=configuration,
        )
    except DIDSConnectionDetailsNotFoundError:
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
            message_override="Document Intelligence DataServer is not available",
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
    Data Server connection details, integrations, and data connections.
    Always returns 200 OK with status indicating configuration state.
    """
    return await _get_document_intelligence_config_response(storage)


@router.post("")
async def upsert_document_intelligence(
    payload: DocumentIntelligenceConfigPayload,
    storage: StorageDependency,
) -> DocumentIntelligenceConfigResponse:
    """Upsert Document Intelligence configuration (PUT semantics).

    Accepts a combined configuration payload under the `/document-intelligence`
    root. It stores the Data Server connection details and any provided
    integrations. For now, integrations are upserted individually by kind.

    Returns the updated configuration in the same format as the GET endpoint.
    """
    # Persist Data Server connection details for DocInt.
    data_sources = payload.to_data_sources()
    await storage.set_dids_connection_details(data_sources.data_server)

    # Initialize or refresh the DI database/datasource
    await _build_datasource(data_sources)

    # Upsert integrations (if provided)
    for integration in payload.to_integrations():
        await storage.set_document_intelligence_integration(integration)

    await storage.set_dids_data_connections(payload.data_connections)

    # Return the updated configuration using the helper method
    return await _get_document_intelligence_config_response(storage)


@router.delete("")
async def clear_document_intelligence(
    storage: StorageDependency,
):
    """Clear the Document Intelligence database."""
    # Check to see if we have the DIDS details in the agentserver database to know
    # if we have state to clear. Don't use the dependency injection so we can
    # suppress a caught error
    conn_details: DataServerDetails
    try:
        conn_details = await storage.get_dids_connection_details()
    except DIDSConnectionDetailsNotFoundError:
        return {"ok": True}

    # Setup the DataSource.
    proper_json = conn_details.as_datasource_connection_input()
    DataSource.setup_connection_from_input_json(proper_json)

    # Try to drop the mindsdb database.
    try:
        ds = DataSource.model_validate(datasource_name="sema4ai")
        ds.execute_sql(f"DROP DATABASE IF EXISTS {DATA_SOURCE_NAME};")
    except Exception as e:
        logger.error("Failed to clear document intelligence", error=str(e))
        if isinstance(e, PlatformHTTPError):
            raise e
        else:
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED, "Failed to clear document intelligence"
            ) from e

    # If we had a datasource, we should also have a Reducto integration.
    try:
        await storage.delete_document_intelligence_integration(IntegrationKind.REDUCTO.value)
    except DocumentIntelligenceIntegrationNotFoundError:
        logger.info("No Reducto integration found to delete, skipping")
        pass

    # Clear the dataserver connection details from the agent-server database.
    await storage.delete_dids_connection_details()

    # Clear the dataserver data connections from the agent-server database.
    await storage.delete_dids_data_connections()

    return {"ok": True}


# Sub-routers wiring
router.include_router(data_models_router)
router.include_router(quality_checks_router)
router.include_router(layouts_router)
router.include_router(documents_router)
router.include_router(jobs_router)
