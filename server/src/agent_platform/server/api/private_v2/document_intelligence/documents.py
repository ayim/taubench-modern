from typing import Any

from fastapi import APIRouter, UploadFile
from reducto.types.shared.parse_response import ResultFullResult as ParseResult
from sema4ai_docint.extraction.reducto.async_ import JobType
from sema4ai_docint.utils import validate_extraction_schema
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from agent_platform.core.document_intelligence.document_layout import IngestDocumentResponse
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads.document_intelligence import (
    ExtractDocumentPayload,
    ExtractJobResult,
    GenerateSchemaResponsePayload,
    JobStartResponsePayload,
    ParseJobResult,
)
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    AsyncExtractionClientDependency,
    DIDependency,
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.api.private_v2.document_intelligence.services import (
    _create_job_result,
    _get_or_upload_file,
    _get_thread_or_404,
    _raise_mapped_reducto_error,
    _resolve_extract_request,
    _upload_and_start_extract,
    _upload_and_start_parse,
)
from agent_platform.server.auth import AuthedUser

logger = get_logger(__name__)


router = APIRouter()


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
