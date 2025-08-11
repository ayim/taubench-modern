from fastapi import APIRouter
from sema4ai.data import DataSource
from sema4ai_docint.models import DocumentLayout, initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence import DIDSConnectionDetails, DocumentLayoutSummary
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import (
    UpsertDocumentIntelligenceConfigPayload,
)
from agent_platform.server.api.dependencies import DocIntDatasourceDependency, StorageDependency
from agent_platform.server.storage.postgres.postgres import PostgresConfig

logger: BoundLogger = get_logger(__name__)


async def _build_datasource(connection_details: DIDSConnectionDetails):
    proper_json = connection_details.as_datasource_connection_input()

    try:
        DataSource.setup_connection_from_input_json(proper_json)

        # Drop existing database if it exists
        # Create admin datasource for administrative commands
        admin_ds = DataSource.model_validate(datasource_name="sema4ai")

        drop_sql = "DROP DATABASE IF EXISTS DocumentIntelligence;"
        admin_ds.execute_sql(drop_sql)

        create_sql = f'''
        CREATE DATABASE DocumentIntelligence
        WITH ENGINE = "postgres",
        PARAMETERS = {{
            "user": "{PostgresConfig.user}",
            "password": "{PostgresConfig.password}",
            "host": "{PostgresConfig.host}",
            "port": {PostgresConfig.port},
            "database": "{PostgresConfig.db}",
            "schema": "docint"
        }};
        '''

        admin_ds.execute_sql(create_sql)

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
    # Persist Data Server connection details
    details = payload.to_dids_connection_details()
    await storage.set_dids_connection_details(details)

    # Initialize or refresh the DI database/datasource
    await _build_datasource(details)

    # Upsert integrations (if provided)
    for integration in payload.to_integrations():
        await storage.set_document_intelligence_integration(integration)

    return {"ok": True}


@router.get("/layouts")
async def get_all_layouts(docint_ds: DocIntDatasourceDependency) -> list[DocumentLayoutSummary]:
    """Get all layouts from the Document Intelligence database."""
    document_layouts = DocumentLayout.find_all(docint_ds)
    layout_summaries = []
    for layout in document_layouts:
        layout_summaries.append(
            DocumentLayoutSummary(
                name=layout.name,
                data_model=layout.data_model,
                summary=layout.summary,
            )
        )
    return layout_summaries
