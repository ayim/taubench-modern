from typing import Any, NoReturn

from fastapi import UploadFile
from reducto.types import ExtractResponse, ParseResponse, SplitResponse
from reducto.types.shared.parse_response import ResultFullResult as ParseResult
from reducto.types.shared.split_response import Result as SplitResult
from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient, Job
from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
    UploadPresignRequestError,
    UploadPutError,
)
from sema4ai_docint.models import DocumentLayout
from sema4ai_docint.models.data_model import DataModel
from structlog import get_logger

from agent_platform.core.document_intelligence.document_layout import (
    ResolvedExtractRequest,
)
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads.document_intelligence import (
    ExtractDocumentPayload,
    ExtractJobResult,
    JobResult,
    ParseJobResult,
    SplitJobResult,
)
from agent_platform.core.payloads.upload_file import UploadFilePayload
from agent_platform.server.api.dependencies import (
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser

logger = get_logger(__name__)


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
