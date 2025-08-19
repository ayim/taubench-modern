import json
from typing import Any, NoReturn

from fastapi import APIRouter, UploadFile
from sema4ai.data import DataSource
from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
    UploadPresignRequestError,
    UploadPutError,
)
from sema4ai_docint.models import DocumentLayout, Mapping, MappingRow, initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name, validate_schema
from starlette.concurrency import run_in_threadpool
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence import (
    DIDSConnectionDetails,
    DocumentLayoutSummary,
)
from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    DataModelPayload,
    UpdateDataModelRequest,
    model_to_spec_dict,
    summary_from_model,
)
from agent_platform.core.document_intelligence.document_layout import (
    DocumentLayoutBridge,
)
from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.files.files import UploadedFile
from agent_platform.core.payloads import (
    DocumentLayoutPayload,
    UpsertDocumentIntelligenceConfigPayload,
)
from agent_platform.core.payloads.document_intelligence import (
    ExtractDocumentPayload,
    GenerateLayoutResponsePayload,
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
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    DocumentIntelligenceIntegrationNotFoundError,
)

logger: BoundLogger = get_logger(__name__)


async def _build_datasource(connection_details: DIDSConnectionDetails):
    proper_json = connection_details.as_datasource_connection_input()

    try:
        DataSource.setup_connection_from_input_json(proper_json)

        # Drop existing database if it exists
        # Create admin datasource for administrative commands
        admin_ds = DataSource.model_validate(datasource_name="sema4ai")

        drop_sql = f"DROP DATABASE IF EXISTS {DATA_SOURCE_NAME};"
        admin_ds.execute_sql(drop_sql)

        # We may support multiple connections in the future, but for now we only support one
        num_data_connections = len(connection_details.data_connections)
        if num_data_connections != 1:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Exactly one data connection is required (got {num_data_connections}).",
            )
        connection = connection_details.data_connections[0]

        # Pass the data connection details directly to the datasource
        create_sql = f'''
        CREATE DATABASE {DATA_SOURCE_NAME}
        WITH ENGINE = "{connection.engine.value}",
        PARAMETERS = {{
            {connection.build_mindsdb_parameters()}
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
        public_message = "We couldn't connect to the document service. Check your credentials."

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
            public_message = "We couldn't connect to the document service. Check your credentials."
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
            public_message = "Backend upload failed unexpectedly."

    elif isinstance(error, UploadMissingPresignedUrlError | UploadMissingFileIdError):
        logger.warning(
            "Reducto upload did not return required fields",
            error=message,
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        error_code = ErrorCode.UNEXPECTED
        public_message = "Backend upload failed unexpectedly."

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
            public_message = "We couldn't connect to the document service. Check your credentials."
        else:
            error_code = ErrorCode.UNEXPECTED
            public_message = "Failed to upload content."

    elif isinstance(error, ExtractFailedError):
        logger.warning(
            "Reducto extract failed",
            error=message,
            reason=getattr(error, "reason", None),
            user_id=user_id,
            thread_id=thread_id,
            file_id=getattr(uploaded_file, "file_id", None),
        )
        error_code = ErrorCode.UNPROCESSABLE_ENTITY
        public_message = "Document extraction failed."

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


@router.delete("")
async def clear_document_intelligence(
    storage: StorageDependency,
):
    """Clear the Document Intelligence database."""
    # Check to see if we have the DIDS details in the agentserver database to know
    # if we have state to clear. Don't use the dependency injection so we can
    # suppress a caught error
    conn_details: DIDSConnectionDetails
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
async def create_data_model(payload: CreateDataModelRequest, docint_ds: DocIntDatasourceDependency):
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

        # Create a default layout for the data model
        upsert_layout_payload = DocumentLayoutPayload.model_validate(
            {
                "data_model_name": created.name,
                "name": f"default_{created.name}",
                "summary": f"Default layout for data model {created.name}",
                "extraction_schema": created.model_schema,
            }
        )
        await upsert_layout(
            payload=upsert_layout_payload,
            docint_ds=docint_ds,
        )
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
    model_name: str, payload: UpdateDataModelRequest, docint_ds: DocIntDatasourceDependency
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


@router.get("/layouts/{layout_name}")
async def get_layout(
    layout_name: str,
    data_model_name: str,
    docint_ds: DocIntDatasourceDependency,
) -> DocumentLayoutBridge:
    """Get a layout by name and data model from the Document Intelligence database."""
    try:
        # Normalize the names
        normalized_layout_name = normalize_name(layout_name)
        normalized_data_model_name = normalize_name(data_model_name)

        # Find the layout in the database
        document_layout = DocumentLayout.find_by_name(
            docint_ds, normalized_data_model_name, normalized_layout_name
        )

        if not document_layout:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{normalized_layout_name}' not found for data "
                f"model '{normalized_data_model_name}'",
            )

        # Convert DocumentLayout to DocumentLayoutBridge
        return DocumentLayoutBridge.from_document_layout(document_layout)

    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error getting layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to get layout") from e


@router.post("/layouts")
async def upsert_layout(
    payload: DocumentLayoutPayload,
    docint_ds: DocIntDatasourceDependency,
):
    """Upsert a layout into the Document Intelligence database.

    Behavior:
    - If a layout with the same name and data model exists, update it
      (extraction schema, translation schema, summary, extraction config, prompt).
    - Otherwise, insert a new layout.
    """
    try:
        normalized = DocumentLayoutPayload.model_validate(payload)

        # Try to find existing layout
        existing = DocumentLayout.find_by_name(
            docint_ds, normalized.data_model_name, normalized.name
        )
        if existing:
            existing.extraction_schema = normalized.extraction_schema
            existing.translation_schema = normalized.wrap_translation_schema()
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


@router.put("/layouts/{layout_name}")
async def update_layout(
    layout_name: str,
    data_model_name: str,
    payload: DocumentLayoutPayload,
    docint_ds: DocIntDatasourceDependency,
):
    """Partially update an existing layout in the Document Intelligence database.

    This is a traditional PUT endpoint that requires the layout to already exist,
    unlike the upsert endpoint which creates if it doesn't exist. It only updates
    the fields in the payload which are not null.
    """
    try:
        normalized_payload = DocumentLayoutPayload.model_validate(payload)

        # Find the existing layout
        existing_layout = DocumentLayout.find_by_name(docint_ds, data_model_name, layout_name)
        if existing_layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{layout_name}' not found for data model '{data_model_name}'",
            )

        # Update the existing layout
        if normalized_payload.extraction_schema is not None:
            existing_layout.extraction_schema = normalized_payload.extraction_schema
        if normalized_payload.translation_schema is not None:
            existing_layout.translation_schema = normalized_payload.wrap_translation_schema()
        if normalized_payload.summary is not None:
            existing_layout.summary = normalized_payload.summary
        if normalized_payload.extraction_config is not None:
            existing_layout.extraction_config = normalized_payload.extraction_config
        if normalized_payload.prompt is not None:
            existing_layout.system_prompt = normalized_payload.prompt

        existing_layout.update(docint_ds)

        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error updating layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Layout update failed unexpectedly") from e


@router.delete("/layouts/{layout_name}")
async def delete_layout(
    layout_name: str,
    data_model_name: str,
    docint_ds: DocIntDatasourceDependency,
):
    """Delete a layout from the Document Intelligence database."""
    try:
        # Normalize the names
        normalized_layout_name = normalize_name(layout_name)
        normalized_data_model_name = normalize_name(data_model_name)

        # Find the layout
        layout = DocumentLayout.find_by_name(
            docint_ds, normalized_data_model_name, normalized_layout_name
        )
        if layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{layout_name}' not found for data model '{data_model_name}'",
            )

        # Delete the layout
        deleted = layout.delete(docint_ds)
        if not deleted:
            raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to delete layout")

        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error deleting layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to delete layout: {e!s}") from e


async def _generate_translation_rules(
    extraction_schema: dict[str, Any],
    data_model_schema: dict[str, Any],
    agent_server_client: AgentServerClientDependency,
):
    """Generate translation rules for a layout."""
    mapping_rules_text = await run_in_threadpool(
        agent_server_client.create_mapping,
        json.dumps(data_model_schema),
        json.dumps(extraction_schema),
    )
    mapping_rules = json.loads(mapping_rules_text)
    if not isinstance(mapping_rules, list):
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="Generated mapping rules are not a list, please try again or provide "
            "a different data model or layout",
        )

    return Mapping(rules=[MappingRow(**rule) for rule in mapping_rules])


async def _generate_layout_name(
    file_name: str,
    agent_server_client: AgentServerClientDependency,
):
    """Generate a layout name for a document."""

    def _sync_generate_layout_name(file_ref: str, client: AgentServerClientDependency):
        images = [img.get("value") for img in client._file_to_images(file_ref)]
        images = [img for img in images if img is not None]
        if len(images) == 0:
            raise ValueError("No images found in the document")

        layout_name = client.generate_document_layout_name(images, file_ref)
        return normalize_name(layout_name)

    try:
        return await run_in_threadpool(_sync_generate_layout_name, file_name, agent_server_client)
    except ValueError as e:
        # Raised if the document is not an image, so the message should be end-user friendly
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Failed to generate layout name: {e!s}.",
        ) from e


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
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    # get data model' schema
    data_model = DataModel.find_by_name(docint_ds, normalize_name(data_model_name))
    if not data_model:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Data model {data_model_name} not found",
        )
    model_schema_json = json.dumps(data_model.model_schema, indent=2)

    # generate extraction schema
    candidate_extraction_schema = await run_in_threadpool(
        agent_server_client.generate_extraction_schema,
        uploaded_file.file_ref,
        model_schema_json,
    )
    try:
        extraction_schema = validate_schema(candidate_extraction_schema)
    except Exception as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="The generated layout schema is not valid. Please try again or provide "
            "a different data model or layout.",
        ) from e

    # Generate Layout name
    layout_name = await _generate_layout_name(uploaded_file.file_ref, agent_server_client)

    # Generate summary for the layout
    summary = await run_in_threadpool(
        agent_server_client.summarize_with_args,
        {
            "Layout name": layout_name,
            "Data model name": data_model.name,
            "Layout schema": extraction_schema,
        },
    )

    # Generate translation rules
    translation_rules = await _generate_translation_rules(
        extraction_schema,
        data_model.model_schema,
        agent_server_client,
    )

    # Generate layout
    layout = DocumentLayoutBridge.model_validate(
        {
            "name": layout_name,
            "data_model": data_model.name,
            "summary": summary,
            "extraction_schema": extraction_schema,
            "translation_schema": translation_rules,
        }
    )

    return GenerateLayoutResponsePayload(
        layout=layout,
        file=uploaded_file if new_file else None,
    )


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


async def _resolve_extract_request(
    payload: ExtractDocumentPayload,
    docint_ds: DocIntDatasourceDependency,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    user: AuthedUser,
) -> tuple[str, UploadedFile, DocumentLayout, str]:
    """Handles the extraction payload.

    If the payload is valid, the returned values will be:
    - thread_id: The thread ID from the payload.
    - uploaded_file: The uploaded file from the payload.
    - document_layout: The document layout from the payload.
    - data_model_prompt: The data model prompt from the payload.
    """
    valid_payload = ExtractDocumentPayload.model_validate(payload)

    thread_id = valid_payload.thread_id
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)
    file, _ = await _get_or_upload_file(
        valid_payload.file_name,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    # Get data model prompt and document layout
    data_model_prompt: str = ""
    document_layout: DocumentLayout | None = None

    data_model: DataModel | None = None
    if valid_payload.data_model_name:
        data_model = DataModel.find_by_name(docint_ds, valid_payload.data_model_name)
        if not data_model:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Data model {valid_payload.data_model_name} not found",
            )
        data_model_prompt = data_model.prompt or ""

    if valid_payload.layout_name:
        if not data_model:
            # This check will likely never happen as we validate the payload before
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required when layout_name is provided",
            )
        document_layout = DocumentLayout.find_by_name(
            docint_ds, data_model.name, valid_payload.layout_name
        )
        if not document_layout:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout {valid_payload.layout_name} not found",
            )
    else:
        # We must have been given a document layout based on payload's initial validation
        if valid_payload.document_layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="document_layout is required when layout_name is not provided",
            )
        document_layout = valid_payload.document_layout.to_document_layout()

    return thread_id, file, document_layout, data_model_prompt


async def _upload_and_extract(  # noqa: PLR0913
    uploaded_file: UploadedFile,
    user_id: str,
    thread_id: str,
    document_layout: DocumentLayout,
    file_manager: FileManagerDependency,
    extraction_client: ExtractionClientDependency,
    data_model_prompt: str | None = None,
):
    """Upload a file and extract it using the Document Intelligence database."""
    try:
        file_contents = await file_manager.read_file_contents(uploaded_file.file_id, user_id)
        reducto_doc_id = extraction_client.upload(file_contents, content_length=len(file_contents))

        # Ready extraction schema
        schema = document_layout.extraction_schema
        if schema is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message="Document layout has no extraction schema",
            )
        schema = dict(schema)

        # Figure out prompt
        prompt = extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT
        if data_model_prompt:
            prompt = f"{prompt}\n\n{data_model_prompt}"
        if document_layout.system_prompt:
            prompt = f"{prompt}\n\n{document_layout.system_prompt}"

        logger.info(
            f"Extracting document {reducto_doc_id} with schema {schema} and prompt {prompt}"
        )
        return extraction_client.extract(
            reducto_doc_id,
            schema=schema,
            system_prompt=prompt,
            extraction_config=document_layout.extraction_config,
        )
    except PlatformHTTPError:
        raise
    except Exception as e:
        _raise_mapped_reducto_error(
            e,
            uploaded_file=uploaded_file,
            user_id=user_id,
            thread_id=thread_id,
        )


@router.post("/documents/extract")
async def extract_document(  # noqa: PLR0913
    user: AuthedUser,
    payload: ExtractDocumentPayload,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: ExtractionClientDependency,
    docint_ds: DocIntDatasourceDependency,
):
    """Extract from an existing document using the Document Intelligence database."""
    # This endpoint deviates from other endpoints because it uses a JSON payload so it
    # cannot accept a multipart/form-data request that includes a file.

    thread_id, file, document_layout, data_model_prompt = await _resolve_extract_request(
        payload=payload,
        docint_ds=docint_ds,
        storage=storage,
        file_manager=file_manager,
        user=user,
    )

    extract_response = await _upload_and_extract(
        uploaded_file=file,
        user_id=user.user_id,
        thread_id=thread_id,
        document_layout=document_layout,
        file_manager=file_manager,
        extraction_client=extraction_client,
        data_model_prompt=data_model_prompt,
    )

    extract_result = extract_response.result
    return extract_result[0]
