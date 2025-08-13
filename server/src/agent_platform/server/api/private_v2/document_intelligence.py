import json
from typing import Any, NoReturn

from fastapi import APIRouter, UploadFile
from sema4ai.data import DataSource
from sema4ai_docint.extraction.reducto.exceptions import (
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
    UploadPresignRequestError,
    UploadPutError,
)
from sema4ai_docint.models import DocumentLayout, initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from starlette.concurrency import run_in_threadpool
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence import (
    DIDSConnectionDetails,
    DocumentLayoutSummary,
)
from agent_platform.core.document_intelligence.data_models import (
    DataModelPayload,
    UpsertDataModelRequest,
    model_to_spec_dict,
    summary_from_model,
)
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import (
    UpsertDocumentIntelligenceConfigPayload,
    UpsertDocumentLayoutPayload,
)
from agent_platform.core.payloads.upload_file import UploadFilePayload
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    DocIntDatasourceDependency,
    ExtractionClientDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
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


def _map_reducto_typed_error(
    error: Exception,
    *,
    uploaded_file: Any,
    user_id: str,
    thread_id: str,
) -> tuple[ErrorCode, str] | None:
    message = str(error)
    error_code: ErrorCode | None = None
    public_message: str | None = None

    if isinstance(error, UploadForbiddenError):
        logger.warning(
            "Reducto unauthorized/forbidden during upload/parse",
            error=message,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        error_code = ErrorCode.UNAUTHORIZED
        public_message = (
            "We couldn't connect to the document service. "
            "Check your credentials or contact support."
        )

    elif isinstance(error, UploadPresignRequestError):
        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            logger.warning(
                "Reducto unauthorized/forbidden during upload presign",
                error=message,
                status_code=status_code,
                user_id=user_id,
                thread_id=thread_id,
                file_id=getattr(uploaded_file, "file_id", None),
            )
            error_code = ErrorCode.UNAUTHORIZED
            public_message = (
                "We couldn't connect to the document service. "
                "Check your credentials or contact support."
            )
        else:
            logger.warning(
                "Reducto upload presign request failed",
                error=message,
                status_code=status_code,
                user_id=user_id,
                thread_id=thread_id,
                file_id=getattr(uploaded_file, "file_id", None),
            )
            error_code = ErrorCode.UNEXPECTED
            public_message = (
                "Backend upload failed unexpectedly. Please try again or contact support."
            )

    elif isinstance(error, UploadMissingPresignedUrlError | UploadMissingFileIdError):
        logger.warning(
            "Reducto upload did not return required fields",
            error=message,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        error_code = ErrorCode.UNEXPECTED
        public_message = "Backend upload failed unexpectedly. Please try again or contact support."

    elif isinstance(error, UploadPutError):
        status_code = getattr(error, "status_code", None)
        logger.warning(
            "Reducto upload PUT failed",
            error=message,
            status_code=status_code,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        if status_code in (401, 403):
            error_code = ErrorCode.UNAUTHORIZED
            public_message = (
                "We couldn't connect to the document service. "
                "Check your credentials or contact support."
            )
        else:
            error_code = ErrorCode.UNEXPECTED
            public_message = "Failed to upload content. Please try again or contact support."

    if error_code is None or public_message is None:
        return None
    return (error_code, public_message)


async def _get_thread_or_404(storage: StorageDependency, user_id: str, thread_id: str):
    """Load a thread or raise a NOT_FOUND HTTP error."""
    thread = await storage.get_thread(user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )
    return thread


async def _get_or_upload_file(
    file: UploadFile | str,
    *,
    thread: Any,
    user_id: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
):
    """Resolve an input file reference or upload a new file.

    Returns a tuple of (uploaded_file, new_file_flag).
    """
    if isinstance(file, str):
        stored_file = await storage.get_file_by_ref(thread, file, user_id)
        if not stored_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (storage)",
            )
        updated_file = await file_manager.refresh_file_paths([stored_file])
        if not updated_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (refresh)",
            )
        return updated_file[0], False

    upload_request = UploadFilePayload(file=file)
    stored_files = await file_manager.upload([upload_request], thread, user_id)
    return stored_files[0], True


def _raise_mapped_reducto_error(
    error: Exception,
    *,
    uploaded_file: Any,
    user_id: str,
    thread_id: str,
) -> NoReturn:
    """Normalize Reducto client errors to PlatformHTTPError and raise."""
    message = str(error)
    logger.error("Document parse failed via Reducto", error=message)

    # Prefer new typed exceptions from the extraction client
    typed_result = _map_reducto_typed_error(
        error,
        uploaded_file=uploaded_file,
        user_id=user_id,
        thread_id=thread_id,
    )
    if typed_result is not None:
        error_code, public_message = typed_result
        raise PlatformHTTPError(error_code, public_message) from error

    if message.startswith("Extract job failed:"):
        reason = message.split(":", 1)[1].strip() if ":" in message else message
        logger.warning(
            "Reducto parse job failed",
            reason=reason,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        raise PlatformHTTPError(
            ErrorCode.UNPROCESSABLE_ENTITY,
            "We couldn't process this file. Please try again or contact support.",
        ) from error

    if message.startswith("Unknown job status:"):
        status_str = message.split(":", 1)[1].strip() if ":" in message else "unknown"
        logger.warning(
            "Reducto returned unknown job status",
            status=status_str,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED,
            (
                "The document service returned an unexpected response. "
                "Please try again or contact support."
            ),
        ) from error

    logger.warning(
        "Unexpected error during document parse",
        error=message,
        user_id=user_id,
        thread_id=thread_id,
        file_id=getattr(uploaded_file, "file_id", None),
    )
    raise PlatformHTTPError(
        ErrorCode.UNEXPECTED,
        "Something went wrong while processing the file. Please try again or contact support.",
    ) from error


async def _upload_and_parse(
    *,
    file_manager: FileManagerDependency,
    extraction_client: ExtractionClientDependency,
    uploaded_file: Any,
    user_id: str,
    thread_id: str,
):
    try:
        file_contents = await file_manager.read_file_contents(uploaded_file.file_id, user_id)
        reducto_uploaded_file_url = extraction_client.upload(
            file_contents, content_length=len(file_contents)
        )
        return extraction_client.parse(reducto_uploaded_file_url)
    except PlatformHTTPError:
        raise
    except Exception as e:
        _raise_mapped_reducto_error(
            e,
            uploaded_file=uploaded_file,
            user_id=user_id,
            thread_id=thread_id,
        )


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


# Document Layout Endpoints


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


@router.post("/layouts")
async def upsert_layout(
    # Payload is a dict because we use dataclasses and want to allow camelCase
    # in the payload and this is the only way to do that via FastAPI without a contrived
    # dependency work around.
    payload: dict,
    docint_ds: DocIntDatasourceDependency,
):
    """Upsert a layout into the Document Intelligence database.

    Behavior:
    - If a layout with the same name and data model exists, update it
      (extraction schema, translation schema, summary, extraction config, prompt).
    - Otherwise, insert a new layout.
    """
    try:
        normalized = UpsertDocumentLayoutPayload.model_validate(payload)

        # Wrap translation schema (array of rules) into DI model-compatible dict
        translation_schema_wrapped = None
        if normalized.translation_schema is not None:
            translation_schema_wrapped = {
                "rules": [rule.to_compact_dict() for rule in normalized.translation_schema]
            }

        # Try to find existing layout
        existing = DocumentLayout.find_by_name(
            docint_ds, normalized.data_model_name, normalized.name
        )
        if existing:
            existing.extraction_schema = normalized.extraction_schema
            existing.translation_schema = translation_schema_wrapped
            existing.summary = normalized.summary
            existing.extraction_config = normalized.extraction_config
            existing.system_prompt = normalized.prompt
            existing.update(docint_ds)
        else:
            layout = normalized.to_document_layout()
            layout.insert(docint_ds)

        return {"ok": True}
    except Exception as e:
        logger.error("Error upserting layout", error=str(e))
        raise PlatformError(ErrorCode.UNEXPECTED, f"Failed to upsert layout: {e!s}") from e


@router.post("/layouts/generate")
async def generate_layout_from_file(  # noqa: PLR0913
    file: UploadFile | str,  # a direct upload or a file ref
    data_model_name: str,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
):
    """Generate a layout from a document."""
    # get thread
    thread = await storage.get_thread(user.user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )

    # get file
    new_file = False
    if isinstance(file, str):
        stored_file = await storage.get_file_by_ref(thread, file, user.user_id)
        if not stored_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (storage)",
            )
        updated_file = await file_manager.refresh_file_paths([stored_file])
        if not updated_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (refresh)",
            )
        uploaded_file = updated_file[0]
    else:
        upload_request = UploadFilePayload(file=file)
        stored_files = await file_manager.upload([upload_request], thread, user.user_id)
        uploaded_file = stored_files[0]
        new_file = True

    # get data model' schema
    data_model = DataModel.find_by_name(docint_ds, normalize_name(data_model_name))
    if not data_model:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Data model {data_model_name} not found",
        )
    model_schema_json = json.dumps(data_model.model_schema, indent=2)

    # generate extraction schema
    extraction_schema = await run_in_threadpool(
        agent_server_client.generate_extraction_schema,
        uploaded_file.file_ref,
        model_schema_json,
    )

    if new_file:
        return {
            "extraction_schema": extraction_schema,
            "uploaded_file": uploaded_file,
        }
    else:
        return {
            "extraction_schema": extraction_schema,
        }


@router.post("/data-models/generate")
async def generate_data_model_from_document(  # noqa: PLR0913
    file: UploadFile | str,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
):
    """Generate a data model from a document."""

    thread = await storage.get_thread(user.user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )

    new_file = False
    if isinstance(file, str):
        stored_file = await storage.get_file_by_ref(thread, file, user.user_id)
        if not stored_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (storage)",
            )
        updated_file = await file_manager.refresh_file_paths([stored_file])
        if not updated_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (refresh)",
            )
        uploaded_file = updated_file[0]
    else:
        upload_request = UploadFilePayload(file=file)
        stored_files = await file_manager.upload([upload_request], thread, user.user_id)
        uploaded_file = stored_files[0]
        new_file = True

    schema = await run_in_threadpool(
        agent_server_client.generate_schema_from_document,
        uploaded_file.file_ref,
    )

    if new_file:
        return {
            "model_schema": schema,
            "uploaded_file": uploaded_file,
        }
    else:
        return {
            "model_schema": schema,
        }


# Reducto (extract, parse ...) endpoints


@router.post("/documents/parse")
async def parse_document(  # noqa: PLR0913
    user: AuthedUser,
    file: UploadFile | str,  # a direct upload or a file ref
    thread_id: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: ExtractionClientDependency,
):
    """Parse a new document using the Document Intelligence database.

    This endpoint is used to parse a new document. To parse a document that already
    exists, use the `/documents/{document_id}/parse` endpoint.
    """
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    parse_response = await _upload_and_parse(
        file_manager=file_manager,
        extraction_client=extraction_client,
        uploaded_file=uploaded_file,
        user_id=user.user_id,
        thread_id=thread_id,
    )

    parse_result = parse_response.result
    result: dict[str, Any] = {"parse_result": parse_result}
    if new_file:
        result["uploaded_file"] = uploaded_file
    return result
