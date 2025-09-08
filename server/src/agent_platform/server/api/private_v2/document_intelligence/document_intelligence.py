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
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import UpsertDocumentIntelligenceConfigPayload
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


router = APIRouter()


@router.get("/ok")
async def ok(docint_ds: DocIntDatasourceDependency):
    return {"ok": True}


@router.post("")
async def upsert_document_intelligence(
    payload: UpsertDocumentIntelligenceConfigPayload,
    storage: StorageDependency,
):
    """Upsert Document Intelligence configuration (PUT semantics).

    Accepts a combined configuration payload under the `/document-intelligence`
    root. It stores the Data Server connection details and any provided
    integrations. For now, integrations are upserted individually by kind.
    """
    # Persist Data Server connection details for DocInt.
    data_sources = payload.to_data_sources()
    await storage.set_dids_connection_details(data_sources.data_server)

    # Initialize or refresh the DI database/datasource
    await _build_datasource(data_sources)

    # Upsert integrations (if provided)
    for integration in payload.to_integrations():
        await storage.set_document_intelligence_integration(integration)

    return {"ok": True}


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

    return {"ok": True}


# Sub-routers wiring
router.include_router(data_models_router)
router.include_router(quality_checks_router)
router.include_router(layouts_router)
router.include_router(documents_router)
router.include_router(jobs_router)
