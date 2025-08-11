from fastapi import APIRouter
from sema4ai.data import DataSource
from sema4ai_docint.models import DocumentLayout, initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from sema4ai_docint.models.data_model import DataModel
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence import DIDSConnectionDetails, DocumentLayoutSummary
from agent_platform.core.document_intelligence.data_models import (
    DataModelPayload,
    UpsertDataModelRequest,
    model_to_spec_dict,
    summary_from_model,
)
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import UpsertDocumentIntelligenceConfigPayload
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


# Data Model Endpoints


@router.get("/data-models")
async def list_data_models(docint_ds: DocIntDatasourceDependency):
    try:
        models = DataModel.find_all(docint_ds)
        return [summary_from_model(m) for m in models]
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to list data models: {e!s}") from e


@router.post("/data-models", status_code=201)
async def create_data_model(payload: UpsertDataModelRequest, docint_ds: DocIntDatasourceDependency):
    try:
        existing = DataModel.find_by_name(docint_ds, payload.dataModel.name)
        if existing is not None:
            raise PlatformHTTPError(
                ErrorCode.CONFLICT, f"Data model already exists: {payload.dataModel.name}"
            )

        normalized = DataModelPayload.model_validate(payload.dataModel)
        model = normalized.to_data_model()
        model.insert(docint_ds)

        created = DataModel.find_by_name(docint_ds, normalized.name)
        if created is None:
            raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to load created data model")
        return {"dataModel": model_to_spec_dict(created)}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to create data model: {e!s}") from e


@router.get("/data-models/{model_name}")
async def get_data_model(model_name: str, docint_ds: DocIntDatasourceDependency):
    try:
        model = DataModel.find_by_name(docint_ds, model_name)
        if model is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")
        return {"dataModel": model_to_spec_dict(model)}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to get data model: {e!s}") from e


@router.put("/data-models/{model_name}")
async def update_data_model(
    model_name: str, payload: UpsertDataModelRequest, docint_ds: DocIntDatasourceDependency
):
    try:
        existing = DataModel.find_by_name(docint_ds, model_name)
        if existing is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")

        if payload.dataModel.description:
            existing.description = payload.dataModel.description
        if payload.dataModel.schema:
            existing.model_schema = payload.dataModel.schema
        if payload.dataModel.views:
            existing.views = payload.dataModel.views
        if payload.dataModel.quality_checks:
            existing.quality_checks = payload.dataModel.quality_checks
        if payload.dataModel.prompt:
            existing.prompt = payload.dataModel.prompt
        if payload.dataModel.summary:
            existing.summary = payload.dataModel.summary

        existing.update(docint_ds)
        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to update data model: {e!s}") from e


@router.delete("/data-models/{model_name}")
async def delete_data_model(model_name: str, docint_ds: DocIntDatasourceDependency):
    try:
        model = DataModel.find_by_name(docint_ds, model_name)
        if model is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")

        deleted = model.delete(docint_ds)
        if not deleted:
            raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to delete data model")
        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to delete data model: {e!s}") from e
