import json
from dataclasses import dataclass
from typing import Any, NoReturn

from fastapi import APIRouter, Request, UploadFile
from reducto.types import ExtractResponse, ParseResponse, SplitResponse
from reducto.types.shared.parse_response import ResultFullResult as ParseResult
from reducto.types.shared.split_response import Result as SplitResult
from sema4ai.data import DataSource
from sema4ai_docint import ValidationRule, ValidationSummary, validate_document_extraction
from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient, Job, JobStatus, JobType
from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
    UploadPresignRequestError,
    UploadPutError,
)
from sema4ai_docint.models import DocumentLayout, Mapping, MappingRow, initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME, PROJECT_NAME
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name, validate_extraction_schema
from starlette.concurrency import run_in_threadpool
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.data_server.data_sources import DataSources
from agent_platform.core.document_intelligence import (
    DocumentLayoutSummary,
)
from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    ExecuteDataQualityChecksRequest,
    GenerateDataQualityChecksRequest,
    GenerateDataQualityChecksResponse,
    UpdateDataModelRequest,
    model_to_spec_dict,
    summary_from_model,
)
from agent_platform.core.document_intelligence.document_layout import (
    IngestDocumentResponse,
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
    ExtractJobResult,
    GenerateLayoutResponsePayload,
    GenerateSchemaResponsePayload,
    JobResult,
    JobStartResponsePayload,
    JobStatusResponsePayload,
    ParseJobResult,
    SplitJobResult,
)
from agent_platform.core.payloads.upload_file import UploadFilePayload
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    AsyncExtractionClientDependency,
    DIDependency,
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser
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
) -> NoReturn:
    """Normalize Reducto client errors to PlatformHTTPError and raise."""
    error_code: ErrorCode | None = None
    public_message: str | None = None

    if isinstance(error, UploadForbiddenError):
        error_code = ErrorCode.UNAUTHORIZED
        public_message = "We couldn't connect to the document service. Check your credentials."

    elif isinstance(error, UploadPresignRequestError):
        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            error_code = ErrorCode.UNAUTHORIZED
            public_message = "We couldn't connect to the document service. Check your credentials."
        else:
            error_code = ErrorCode.UNEXPECTED
            public_message = "Backend upload failed unexpectedly."

    elif isinstance(error, UploadMissingPresignedUrlError | UploadMissingFileIdError):
        error_code = ErrorCode.UNEXPECTED
        public_message = "Backend upload failed unexpectedly."

    elif isinstance(error, UploadPutError):
        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            error_code = ErrorCode.UNAUTHORIZED
            public_message = "We couldn't connect to the document service. Check your credentials."
        else:
            error_code = ErrorCode.UNEXPECTED
            public_message = "Failed to upload content."

    elif isinstance(error, ExtractFailedError):
        error_code = ErrorCode.UNPROCESSABLE_ENTITY
        public_message = "Document extraction failed."

    if error_code is None or public_message is None:
        error_code = ErrorCode.UNEXPECTED
        public_message = "Something went wrong while processing the file."

    raise PlatformHTTPError(error_code, public_message) from error


async def _upload_and_start_parse(
    *,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClient,
    uploaded_file: Any,
    user_id: str,
    thread_id: str,
) -> Job:
    """Upload file and start parse job using AsyncExtractionClient.

    Args:
        file_manager: File manager dependency
        extraction_client: Async extraction client instance
        uploaded_file: The uploaded file to parse
        user_id: User ID
        thread_id: Thread ID

    Returns:
        Job handle for the parse operation
    """
    try:
        file_contents = await file_manager.read_file_contents(uploaded_file.file_id, user_id)
        reducto_uploaded_file_url = await extraction_client.upload(
            file_contents, content_length=len(file_contents)
        )

        return await extraction_client.start_parse(reducto_uploaded_file_url)
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            f"Document parse failed via Reducto (uploaded_file={uploaded_file!s}, "
            f"user_id={user_id}, thread_id={thread_id}): {e!s}",
            error=str(e),
        )
        _raise_mapped_reducto_error(e)


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
async def create_data_model(
    payload: CreateDataModelRequest,
    docint_ds: DocIntDatasourceDependency,
    di_service: DIDependency,
) -> dict[str, Any]:
    try:
        existing = DataModel.find_by_name(docint_ds, payload.data_model.name)
        if existing is not None:
            raise PlatformHTTPError(
                ErrorCode.CONFLICT, f"Data model already exists: {payload.data_model.name}"
            )

        result = await run_in_threadpool(
            di_service.data_model.create_from_schema,
            normalize_name(payload.data_model.name),
            payload.data_model.description,
            json.dumps(payload.data_model.schema),
        )
        model = DataModel.find_by_name(docint_ds, result["name"])
        if model is None:
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED, f"Data model not found: {payload.data_model.name}"
            )
        return {"data_model": model_to_spec_dict(model)}
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
        return {"data_model": model_to_spec_dict(model)}
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

        if payload.data_model.description:
            existing.description = payload.data_model.description
        if payload.data_model.schema:
            existing.model_schema = payload.data_model.schema
        if payload.data_model.views:
            existing.views = payload.data_model.views
        if payload.data_model.quality_checks:
            existing.quality_checks = payload.data_model.quality_checks
        if payload.data_model.prompt:
            existing.prompt = payload.data_model.prompt
        if payload.data_model.summary:
            existing.summary = payload.data_model.summary

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


@router.post("/quality-checks/generate")
async def generate_quality_checks(
    payload: GenerateDataQualityChecksRequest,
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
) -> GenerateDataQualityChecksResponse:
    try:
        data_model_name = normalize_name(payload.data_model_name)
        data_model = DataModel.find_by_name(docint_ds, data_model_name)
        if not data_model:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {data_model_name}")
        views = data_model.views
        if not views:
            raise PlatformHTTPError(
                ErrorCode.NOT_FOUND,
                f"No views have been defined for the data model: {payload.data_model_name}",
            )
        validation_rules = await run_in_threadpool(
            agent_server_client.generate_validation_rules,
            rules_description=payload.description,
            data_model=data_model,
            datasource=docint_ds,
            database_name=PROJECT_NAME,
            limit_count=payload.limit,
        )
        # we only return the first `limit` rules,
        # so we need to log a warning if we didn't generate enough
        if len(validation_rules) < payload.limit:
            logger.warning(
                f"Generated {len(validation_rules)} data quality checks, expected {payload.limit}"
            )
        final_validation_rules = [ValidationRule.model_validate(rule) for rule in validation_rules]
        return GenerateDataQualityChecksResponse(quality_checks=final_validation_rules)
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED, f"Failed to generate data quality checks: {e!s}"
        ) from e


@router.post("/quality-checks/execute")
async def execute_quality_checks(
    payload: ExecuteDataQualityChecksRequest,
    docint_ds: DocIntDatasourceDependency,
) -> ValidationSummary:
    try:
        validation_summary = validate_document_extraction(
            payload.document_id, docint_ds, payload.quality_checks
        )
        return validation_summary
    except Exception as e:
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED, f"Failed to execute data quality checks: {e!s}"
        ) from e


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
) -> DocumentLayoutPayload:
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

        # Convert DocumentLayout to DocumentLayoutPayload
        return DocumentLayoutPayload.model_validate(document_layout)

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

        # Try to find existing layout (ensure required fields are present)
        if normalized.data_model_name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required for document layout creation",
            )
        if normalized.name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="name is required for document layout creation",
            )

        existing = DocumentLayout.find_by_name(
            docint_ds, normalized.data_model_name, normalized.name
        )
        if existing:
            existing.extraction_schema = (
                normalized.extraction_schema.model_dump(mode="json", exclude_none=True)
                if normalized.extraction_schema
                else None
            )
            existing.translation_schema = normalized.wrap_translation_schema()
            existing.summary = normalized.summary
            existing.extraction_config = normalized.extraction_config
            existing.system_prompt = normalized.prompt
            existing.update(docint_ds)
        else:
            layout = normalized.to_document_layout()
            layout.insert(docint_ds)

        return {"ok": True}
    except PlatformHTTPError:
        raise
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
            existing_layout.extraction_schema = (
                normalized_payload.extraction_schema.model_dump(mode="json", exclude_none=True)
                if normalized_payload.extraction_schema
                else None
            )
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
) -> GenerateLayoutResponsePayload:
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
        agent_server_client.generate_schema,
        uploaded_file.file_ref,
        model_schema_json,
    )
    try:
        extraction_schema = validate_extraction_schema(candidate_extraction_schema)
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
    layout = DocumentLayoutPayload.model_validate(
        {
            "name": layout_name,
            "data_model_name": data_model.name,
            "summary": summary,
            "extraction_schema": extraction_schema,
            "translation_schema": translation_rules,
            # We don't generate some fields OOTB.
            "extraction_config": None,
            "prompt": None,
            # These fields are only set when being persisted into the database.
            "created_at": None,
            "updated_at": None,
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
        agent_server_client.generate_schema,
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


@router.post("/documents/generate-schema")
async def generate_extraction_schema_from_document(  # noqa: PLR0913
    file: UploadFile | str,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    agent_server_client: AgentServerClientDependency,
) -> GenerateSchemaResponsePayload:
    """Generate an extraction schema from a document."""
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    try:
        schema = await run_in_threadpool(
            agent_server_client.generate_schema,
            uploaded_file.file_ref,
        )

        return GenerateSchemaResponsePayload(
            schema=validate_extraction_schema(schema),
            file=uploaded_file if new_file else None,
        )
    except Exception as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="Failed to generate extraction schema",
        ) from e


# Reducto (extract, parse ...) endpoints


@router.post("/documents/parse")
async def parse_document(  # noqa: PLR0913
    user: AuthedUser,
    file: UploadFile | str,  # a direct upload or a file ref
    thread_id: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClientDependency,
) -> ParseResult:
    """Parse a new document using the Document Intelligence database.

    This endpoint is used to parse a new document. It now uses the async client
    for better server performance.
    """
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    job = await _upload_and_start_parse(
        file_manager=file_manager,
        extraction_client=extraction_client,
        uploaded_file=uploaded_file,
        user_id=user.user_id,
        thread_id=thread_id,
    )

    # For synchronous parse, wait for completion (unlike get_job_result endpoint)
    try:
        result = await job.result(poll_interval=3.0)
        job_result = _create_job_result(result)
        if isinstance(job_result, ParseJobResult):
            return job_result.result
        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message="Parse response is not a ParseJobResult",
            )
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            f"Document parse failed via Reducto (uploaded_file={uploaded_file!s}, "
            f"user_id={user.user_id}, thread_id={thread_id}): {e!s}",
            error=str(e),
        )
        _raise_mapped_reducto_error(e)


@router.post("/documents/parse/async")
async def parse_document_async(  # noqa: PLR0913
    user: AuthedUser,
    file: UploadFile | str,  # a direct upload or a file ref
    thread_id: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClientDependency,
) -> JobStartResponsePayload:
    """Parse a document asynchronously, returning a job handle.

    This endpoint immediately returns a job handle that can be used to track
    the parsing progress and retrieve results when complete.

    Returns:
        A response containing:
        - job_id: The ID of the parsing job
        - job_type: The type of job ("parse")
        - uploaded_file: The uploaded file info (if a new file was uploaded)

    Note:
        When checking job status or results, pass job_type="parse" as a query parameter.
    """
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    job = await _upload_and_start_parse(
        file_manager=file_manager,
        extraction_client=extraction_client,
        uploaded_file=uploaded_file,
        user_id=user.user_id,
        thread_id=thread_id,
    )

    return JobStartResponsePayload(
        job_id=job.job_id,
        job_type=JobType.PARSE,
        uploaded_file=uploaded_file if new_file else None,
    )


async def _get_data_model_prompt_and_document_layout(
    payload: ExtractDocumentPayload,
    docint_ds: DocIntDatasourceDependency,
) -> tuple[str, DocumentLayout]:
    """Get the data model prompt and document layout from the payload."""
    data_model_prompt: str = ""
    document_layout: DocumentLayout | None = None

    # Handle layout_name approach (requires data_model_name)
    if payload.layout_name:
        if not payload.data_model_name:
            # This should not happen as we validate the payload before, but needed for type safety
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required when layout_name is provided",
            )

        data_model = DataModel.find_by_name(docint_ds, payload.data_model_name)
        if not data_model:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Data model {payload.data_model_name} not found",
            )
        data_model_prompt = data_model.prompt or ""

        document_layout = DocumentLayout.find_by_name(
            docint_ds, data_model.name, payload.layout_name
        )
        if not document_layout:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout {payload.layout_name} not found",
            )

        return data_model_prompt, document_layout
    else:
        # We must have a document_layout
        if payload.document_layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="document_layout is required when layout_name is not provided",
            )

        # For extraction requests, we can use a partial document layout without name/data_model_name
        # We'll create a minimal DocumentLayout object with just the extraction fields
        extraction_schema = (
            payload.document_layout.extraction_schema.model_dump(mode="json", exclude_none=True)
            if payload.document_layout.extraction_schema
            else None
        )
        document_layout = DocumentLayout(
            name=payload.document_layout.name or "extraction_layout",
            data_model=payload.document_layout.data_model_name or "extraction_model",
            extraction_schema=extraction_schema,
            translation_schema=payload.document_layout.wrap_translation_schema(),
            summary=payload.document_layout.summary,
            extraction_config=payload.document_layout.extraction_config,
            system_prompt=payload.document_layout.prompt,
        )

        # Get data model prompt if data_model_name was provided
        if payload.data_model_name:
            data_model = DataModel.find_by_name(docint_ds, payload.data_model_name)
            if not data_model:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Data model {payload.data_model_name} not found",
                )
            data_model_prompt = data_model.prompt or ""

        return data_model_prompt, document_layout


@dataclass
class ResolvedExtractRequest:
    thread_id: str
    uploaded_file: UploadedFile
    extraction_schema: dict[str, Any]
    extraction_system_prompt: str | None
    extraction_config: dict[str, Any] | None
    data_model_prompt: str | None


async def _resolve_extract_request(
    payload: ExtractDocumentPayload,
    docint_ds: DocIntDatasourceDependency,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    user: AuthedUser,
) -> ResolvedExtractRequest:
    """Handles the extraction payload.

    If the payload is valid, the returned values will be resolved from the payload or the
    document layout as a ResolvedExtractRequest object.
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

    # Get the data model prompt and document layout (handles both new and legacy approaches)
    data_model_prompt, document_layout = await _get_data_model_prompt_and_document_layout(
        valid_payload, docint_ds
    )

    # Extract the fields from the document layout
    extraction_schema = document_layout.extraction_schema
    extraction_system_prompt = document_layout.system_prompt
    extraction_config = document_layout.extraction_config

    if extraction_schema is None:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="extraction_schema could not be resolved from the payload or "
            "the document layout",
        )

    return ResolvedExtractRequest(
        thread_id=thread_id,
        uploaded_file=file,
        extraction_schema=extraction_schema,
        extraction_system_prompt=extraction_system_prompt,
        extraction_config=extraction_config,
        data_model_prompt=data_model_prompt,
    )


async def _upload_and_start_extract(
    request: ResolvedExtractRequest,
    user_id: str,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClient,
) -> Job:
    """Async version of upload and extract using AsyncExtractionClient.

    Args:
        request: The resolved extract request
        user_id: User ID
        file_manager: File manager dependency
        extraction_client: Async extraction client instance
    """
    try:
        file_contents = await file_manager.read_file_contents(
            request.uploaded_file.file_id, user_id
        )
        reducto_doc_id = await extraction_client.upload(
            file_contents, content_length=len(file_contents)
        )

        # Figure out prompt
        prompt = extraction_client.DEFAULT_EXTRACT_SYSTEM_PROMPT
        if request.data_model_prompt:
            prompt = f"{prompt}\n\n{request.data_model_prompt}"
        if request.extraction_system_prompt:
            prompt = f"{prompt}\n\n{request.extraction_system_prompt}"

        logger.info(
            f"Extracting document {reducto_doc_id} with schema {request.extraction_schema} "
            f"and prompt {prompt}"
        )

        return await extraction_client.start_extract(
            reducto_doc_id,
            schema=request.extraction_schema,
            system_prompt=prompt,
            extraction_config=request.extraction_config,
        )
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            f"Document extract failed via Reducto (uploaded_file={request.uploaded_file!s}, "
            f"user_id={user_id}, thread_id={request.thread_id}): {e!s}",
            error=str(e),
        )
        _raise_mapped_reducto_error(e)


@router.post("/documents/extract")
async def extract_document(  # noqa: PLR0913
    user: AuthedUser,
    payload: ExtractDocumentPayload,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClientDependency,
    docint_ds: DocIntDatasourceDependency,
) -> dict[str, Any]:
    """Extract structured data from an existing document.

    Returns extracted data formatted according to the document's data model schema.
    """
    # This endpoint deviates from other endpoints because it uses a JSON payload so it
    # cannot accept a multipart/form-data request that includes a file.

    request = await _resolve_extract_request(
        payload=payload,
        docint_ds=docint_ds,
        storage=storage,
        file_manager=file_manager,
        user=user,
    )

    extract_response = await _upload_and_start_extract(
        request=request,
        user_id=user.user_id,
        file_manager=file_manager,
        extraction_client=extraction_client,
    )

    try:
        result = await extract_response.result(poll_interval=3.0)
        job_result = _create_job_result(result)
        if isinstance(job_result, ExtractJobResult):
            return job_result.result
        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message="Extract response is not a ExtractJobResult",
            )
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            f"Document extract failed via Reducto (uploaded_file={request.uploaded_file!s}, "
            f"user_id={user.user_id}, thread_id={request.thread_id}): {e!s}",
            error=str(e),
        )
        _raise_mapped_reducto_error(e)


@router.post("/documents/extract/async")
async def extract_document_async(  # noqa: PLR0913
    user: AuthedUser,
    payload: ExtractDocumentPayload,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClientDependency,
    docint_ds: DocIntDatasourceDependency,
) -> JobStartResponsePayload:
    """Extract from a document asynchronously, returning a job handle.

    This endpoint immediately returns a job handle that can be used to track
    the extraction progress and retrieve results when complete.

    Returns:
        A response containing:
        - job_id: The ID of the extraction job
        - job_type: The type of job ("extract")

    Note:
        When checking job status or results, pass job_type="extract" as a query parameter.
    """
    request = await _resolve_extract_request(
        payload=payload,
        docint_ds=docint_ds,
        storage=storage,
        file_manager=file_manager,
        user=user,
    )

    job = await _upload_and_start_extract(
        request=request,
        user_id=user.user_id,
        file_manager=file_manager,
        extraction_client=extraction_client,
    )

    return JobStartResponsePayload(
        job_id=job.job_id,
        job_type=JobType.EXTRACT,
    )


# Job Management Endpoints


def _create_job_result(result: Any) -> JobResult:
    """Create the appropriate JobResult type based on the result object type.

    Args:
        job_type: The type of job (used for error context only)
        result: The raw result from the async client

    Returns:
        The properly typed JobResult (ParseJobResult, ExtractJobResult, or SplitJobResult)

    Raises:
        PlatformHTTPError: If the result type is unexpected
    """
    match result:
        case ParseResponse(result=ParseResult() as parse_result):
            return ParseJobResult(result=parse_result)
        case ExtractResponse() as extract_resp:
            # Reducto's ExtractResponse is just a list of objects so we can't easily type it,
            # though it should match the data model's schema.
            return ExtractJobResult(result=extract_resp.result[0])  # type: ignore
        case SplitResponse(result=SplitResult() as split_result):
            return SplitJobResult(result=split_result)
        case _:
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED,
                f"Unexpected result type {type(result)}",
            )


@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    job_type: JobType,
    request: Request,
    user: AuthedUser,
    extraction_client: AsyncExtractionClientDependency,
) -> JobStatusResponsePayload:
    """Get the status of an asynchronous job.

    Args:
        job_id: The ID of the job
        job_type: The type of job (JobType.PARSE, JobType.EXTRACT, or JobType.SPLIT)

    Returns:
        A response containing:
        - job_id: The ID of the job
        - status: The current status ("Pending", "Idle", "Completed", "Failed")
        - result_url: URL to fetch the result (only present when status is "Completed")
    """
    try:
        # Reconstruct the Job object
        job = Job(job_id=job_id, job_type=job_type, client=extraction_client)
        status = await job.status()

        # Construct result URL if job is completed
        result_url = None
        if status == JobStatus.COMPLETED:
            # Construct the URL to the result endpoint
            base_url = str(request.url_for("get_job_result", job_id=job_id))
            result_url = f"{base_url}?job_type={job_type.value}"

        return JobStatusResponsePayload(
            job_id=job_id,
            status=status,
            result_url=result_url,
        )
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            f"Job {job_id} not found or inaccessible",
        ) from e


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    job_type: JobType,
    user: AuthedUser,
    extraction_client: AsyncExtractionClientDependency,
) -> JobResult:
    """Get the result of a completed asynchronous job.

    This endpoint returns immediately based on the current job status:
    HTTP Status Codes:
        200: Job completed successfully - returns JobResult
        404: Job not found OR result not available yet (job still processing)
        422: Job failed

    Args:
        job_id: The ID of the job
        job_type: The type of job (JobType.PARSE, JobType.EXTRACT, or JobType.SPLIT)

    Returns:
        The job result (parse or extract result) when complete.
        For parse jobs, this returns the localized parse response.
        For extract jobs, this returns the extraction results.

    Raises:
        PlatformHTTPError: If the job is still processing, failed, or not found.
    """
    try:
        # Reconstruct the Job object with proper type information
        job = Job(job_id=job_id, job_type=job_type, client=extraction_client)

        # Check job status first
        status = await job.status()

        match status:
            case JobStatus.COMPLETED:
                # Job is complete, get result without polling
                result = await job.result()  # This should return immediately since job is done
                return _create_job_result(result)
            case JobStatus.PENDING | JobStatus.IDLE:
                # Job still processing - result resource doesn't exist yet
                raise PlatformHTTPError(
                    ErrorCode.NOT_FOUND,
                    "Job result not available yet - job is still processing",
                )
            case JobStatus.FAILED:
                # Job failed - return 422
                raise PlatformHTTPError(
                    ErrorCode.UNPROCESSABLE_ENTITY,
                    f"Job {job_id} failed",
                )
            case _:
                # Unknown status
                raise PlatformHTTPError(
                    ErrorCode.UNEXPECTED,
                    f"Unknown job status: {status}",
                )

    except PlatformHTTPError:
        # Re-raise PlatformHTTPErrors (including our status-based errors above)
        raise
    except ExtractFailedError as e:
        logger.error(f"Job {job_id} extraction failed: {e}")
        reason = getattr(e, "reason", None)
        raise PlatformHTTPError(
            ErrorCode.UNPROCESSABLE_ENTITY,
            f"Job {job_id} failed: {reason or str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to get job result for {job_id}: {e}")
        raise PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            f"Job {job_id} not found or inaccessible",
        ) from e


@router.post("/documents/ingest")
async def ingest_document(  # noqa: PLR0913
    user: AuthedUser,
    file: str | UploadFile,
    thread_id: str,
    data_model_name: str,
    layout_name: str,
    storage: StorageDependency,
    docint_ds: DocIntDatasourceDependency,
    file_manager: FileManagerDependency,
    di_service: DIDependency,
) -> IngestDocumentResponse:
    """Ingest a new document into the Document Intelligence database."""
    # get thread
    thread = await storage.get_thread(user.user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )
    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    try:
        response_data = await run_in_threadpool(
            di_service.document.ingest,
            uploaded_file.file_ref,
            data_model_name,
            layout_name,
        )
        return IngestDocumentResponse.model_validate(
            response_data,
            uploaded_file if new_file else None,
        )

    except Exception as e:
        logger.error(f"Error processing document: {e!s}")
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message=f"Failed to process document: {e!s}",
        ) from e
