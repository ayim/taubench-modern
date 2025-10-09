from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from sema4ai.data import DataSource
from sema4ai_docint.models import initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.data_connections import DataSources
from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.responses import ErrorCode, ErrorResponse
from agent_platform.core.integrations import Integration
from agent_platform.core.integrations.settings.data_server import (
    DataServerEndpoint,
    DataServerSettings,
)
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.payloads import DocumentIntelligenceConfigPayload
from agent_platform.core.payloads.data_connection import DataConnectionTag
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
from agent_platform.server.data_server.data_source import initialize_data_source
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
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


async def _build_datasource(data_sources: DataSources):
    """
    Initialize the Document Intelligence database in the Data Server.
    """
    try:
        # Use the server-side initialize_data_source function
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
        # Get all integrations from the new v2_integration table
        all_integrations = await storage.list_integrations()

        # Separate data server integration from other integrations
        data_server_integration = None
        other_integrations = []

        for integration in all_integrations:
            if integration.kind == IntegrationKind.DATA_SERVER:
                data_server_integration = integration
            else:
                other_integrations.append(integration)

        # Get data connections with 'data_intelligence' tag
        all_data_connections = await storage.get_data_connections()
        data_connections = [dc for dc in all_data_connections if "data_intelligence" in dc.tags]

        # Check if we have a data server integration
        if data_server_integration is None:
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
            data_server_integration=data_server_integration,
            integrations=other_integrations,
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
    integrations using the new v2_integration table.

    Returns the updated configuration in the same format as the GET endpoint.
    """
    # Validate that only one data connection ID is provided
    if payload.data_connection_id and len(payload.data_connection_id.strip()) == 0:
        error_response = ErrorResponse(
            ErrorCode.UNPROCESSABLE_ENTITY,
            message_override=(
                "data_connection_id cannot be empty. "
                "Please provide a valid data connection ID or None."
            ),
        )
        return DocumentIntelligenceConfigResponse(
            status=DocumentIntelligenceConfigStatus.ERROR,
            error=error_response.model_dump(),
            configuration=None,
        )

    if payload.data_connection_id:
        try:
            data_connection = await storage.get_data_connection(payload.data_connection_id)
            payload_with_connection = DocumentIntelligenceConfigPayload(
                data_server=payload.data_server,
                integrations=payload.integrations,
                data_connections=[data_connection],
                data_connection_id=payload.data_connection_id,
            )
            data_sources = payload_with_connection.to_data_sources()
        except Exception as e:
            raise PlatformError(
                ErrorCode.NOT_FOUND,
                f"Data connection with ID {payload.data_connection_id} not found: {e}",
            ) from e
    else:
        # No data connection ID provided, use empty data sources
        data_sources = payload.to_data_sources()

    # Initialize or refresh the DI database/datasource
    await _build_datasource(data_sources)

    # Upsert data server integration
    data_server_endpoints = [
        DataServerEndpoint(
            host=endpoint.host,
            port=endpoint.port,
            kind=endpoint.kind.value,
        )
        for endpoint in data_sources.data_server.data_server_endpoints
    ]

    data_server_settings = DataServerSettings(
        username=data_sources.data_server.username or "",
        password=data_sources.data_server.password_str or "",
        endpoints=data_server_endpoints,
    )

    data_server_integration = Integration(
        id=str(uuid4()), kind="data_server", settings=data_server_settings
    )
    await storage.upsert_integration(data_server_integration)

    # Upsert other integrations (if provided)
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

        doc_int_integration = Integration(
            id=str(uuid4()), kind=str(integration_input.type), settings=reducto_settings
        )
        await storage.upsert_integration(doc_int_integration)

    # Remove the data_intelligence tag from all existing data connections
    await storage.clear_data_connection_tag(DataConnectionTag.DOCUMENT_INTELLIGENCE)

    if payload.data_connection_id:
        await storage.add_data_connection_tag(
            payload.data_connection_id, DataConnectionTag.DOCUMENT_INTELLIGENCE
        )

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

    # Remove 'data_intelligence' tag from all data connections
    await storage.clear_data_connection_tag(DataConnectionTag.DOCUMENT_INTELLIGENCE)

    return {"ok": True}


# Sub-routers wiring
router.include_router(data_models_router)
router.include_router(quality_checks_router)
router.include_router(layouts_router)
router.include_router(documents_router)
router.include_router(jobs_router)
