from typing import Annotated, Any, cast

from fastapi import APIRouter, UploadFile
from fastapi.params import Query
from pydantic import BaseModel, Field
from sema4ai_docint.extraction.reducto.async_ import JobType
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
    AsyncExtractionClientDependency,
    CachingDIServiceDependency,
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
from agent_platform.server.cache import CacheKeyStrategy, ThreadFileCache

logger = get_logger(__name__)


router = APIRouter()


class GenerateSchemaPayload(BaseModel):
    """Payload for generate-schema endpoint."""

    instructions: str = Field(default="", description="Optional instructions for schema generation")


CITATION_CORRELATION_DOCS = """The citations included with results from this endpoint can be
correlated to the schema fields based on their types.

Example citation for a simple field in an object:

```json
{
    // this key will be the same key as the schema field
    "sample_extracted_field": [
        {
            "bbox": {
                "left": 0.1,
                "top": 0.2,
                "width": 0.3,
                "height": 0.05,
                "page": 1,
                "original_page": 1
            },
            "confidence": "high",
            "content": "granular citation",
            "image_url": null,
            // Parent block will likely match a similar parse block in the document
            "parentBlock": {
                "bbox": {
                    "left": 0.1,
                    "top": 0.9,
                    "width": 0.8,
                    "height": 0.05,
                    "page": 1
                },
                "block_type": "Text",
                "confidence": "high",
                "content": "This is the full sentence with the granular citation."
            },
            "type": "Text"
        }
    ]
}
```

Example extracted results for a schema field defined as `array` of objects:

```json
{
    "sample_extracted_field": [
        {
            "key1": "value1",
            "key2": "value2"
        }
    ]
}
```

Corresponding citation object:

```json
{
    "sample_extracted_field": [
        {
            "key1": [
                {
                    "bbox": {
                        "left": 0.1,
                        "top": 0.2,
                        "width": 0.3,
                        "height": 0.05,
                    },
                    ... // other citation object fields, see above
                }
            ],
            "key2": [
                {
                    "bbox": {
                        "left": 0.1,
                        "top": 0.2,
                        "width": 0.3,
                        "height": 0.05,
                    },
                    ... // other citation object fields, see above
                }
            ]
        }
    ]
}
```
"""


class SchemaCacheKeyStrategy(CacheKeyStrategy):
    """Cache key strategy for document schema generation.

    Generates cache file names based on the source document's file reference.
    The instructions parameter is not included in the cache key itself, but is
    used by the validate_fn to check if the cached schema is still valid.
    """

    def generate_key(self, file_ref: str, prompt: str = "") -> str:
        """Generate cache key from the document file reference.

        Args:
            file_ref: The file reference of the source document

        Returns:
            Cache file name in the format: {file_ref}.schema.json
        """
        return f"{file_ref}.schema.json"


class SchemaWithPrompt(BaseModel):
    extract_schema: dict[str, Any] = Field(default_factory=dict)


class ExtractedDocumentKeyStrategy(CacheKeyStrategy):
    """Cache key strategy for extracted document.

    Generates cache file names based on the source document's file reference.
    """

    def generate_key(
        self,
        file_ref: str,
        extract_schema: dict[str, Any],
        system_prompt: str = "",
        extraction_config: dict[str, Any] | None = None,
    ) -> str:
        """Generate cache key from the document file reference.

        Args:
            file_ref: The file reference of the source document

        Returns:
            Cache file name in the format: {file_ref}.extracted.json
        """
        return f"{file_ref}.extracted.json"


class ExtractedDocument(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    job_id: str = Field()
    extract_schema: dict[str, Any] = Field()
    citations: dict[str, Any] | None = Field(default=None)
    system_prompt: str | None = Field(default=None)
    extraction_config: dict[str, Any] | None = Field(default=None)


# Decorator to add citation documentation to extraction endpoints
def add_citation_docs(func):
    """Decorator that adds citation correlation documentation to endpoint docstrings."""
    original_doc = func.__doc__ or ""
    func.__doc__ = original_doc + CITATION_CORRELATION_DOCS
    return func


@router.get("/documents/schema")
async def get_extraction_schema_for_document(
    user: AuthedUser,
    file_name: Annotated[str, Query(description="The file name/reference to get the schema for")],
    agent_id: str,
    thread_id: str,
    storage: StorageDependency,
    di_service_with_persistence: CachingDIServiceDependency,
) -> GenerateSchemaResponsePayload:
    """Get a cached extraction schema for a document.

    This endpoint retrieves a previously generated schema from the cache.
    If no schema exists for the given file, returns 404.
    """
    from sema4ai_docint import DIService

    # Get the thread
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    # Verify the file exists in thread storage
    file = await storage.get_file_by_ref(thread, file_name, user.user_id)
    if not file:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"File {file_name} not found in thread {thread_id}",
        )

    di_service = cast(DIService, di_service_with_persistence)

    # Get cached schema using DIService
    doc = await di_service.document_v2.new_document(file.file_ref)
    schema = await di_service.document_v2.get_schema(doc)

    if schema is None:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"No cached schema found for file {file_name}",
        )

    # Return the schema to the caller
    return GenerateSchemaResponsePayload(schema=schema)


@router.post("/documents/generate-schema")
async def generate_extraction_schema_from_document(
    user: AuthedUser,
    agent_id: str,
    thread_id: str,
    file_ref: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    di_service_with_persistence: CachingDIServiceDependency,
    force: Annotated[bool, Query(description="Force re-generation of the schema.")] = False,
    payload: GenerateSchemaPayload | None = None,
) -> GenerateSchemaResponsePayload:
    """Generate an extraction schema from a document.

    This endpoint uses DIService with automatic caching. Schemas are cached in thread
    storage and reused unless force=True is specified.
    """
    from sema4ai_docint import DIService

    instructions = payload.instructions if payload else ""

    # Get the thread
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    # Always put the file in Agent thread storage
    uploaded_file, _ = await _get_or_upload_file(
        file_ref,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    di_service = cast(DIService, di_service_with_persistence)

    # Generate schema using DIService with automatic caching
    doc = await di_service.document_v2.new_document(uploaded_file.file_ref)
    schema = await di_service.document_v2.generate_schema(
        doc,
        force_reload=force,
        user_prompt=instructions,
    )

    # Return the schema to the caller
    return GenerateSchemaResponsePayload(schema=schema)


@router.post("/documents/parse")
async def parse_document(
    user: AuthedUser,
    agent_id: str,
    thread_id: str,
    file_ref: str,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    di_service_with_persistence: CachingDIServiceDependency,
) -> ParseJobResult:
    """Parse a new document using the Document Intelligence database.

    This endpoint is used to parse a new document. It now uses the async client
    for better server performance.
    """
    from reducto.types import ParseResponse
    from sema4ai_docint import DIService

    # Get the thread
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    # Always put the file in Agent thread storage
    uploaded_file, _ = await _get_or_upload_file(
        file_ref,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    di_service = cast(DIService, di_service_with_persistence)

    # Create a new document
    doc = await di_service.document_v2.new_document(uploaded_file.file_ref)
    parse_response: ParseResponse = await di_service.document_v2.parse(doc, force_reload=False)

    job_result = _create_job_result(parse_response, parse_response.job_id)
    if not isinstance(job_result, ParseJobResult):
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"Parse response is not a ParseJobResult (was {type(job_result)})",
        )
    return job_result


@router.post("/documents/parse/async")
async def parse_document_async(
    user: AuthedUser,
    thread_id: str,
    file_ref: str,
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
        file_ref,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    # TODO migrate this to the same impl as /documents/parse
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
@add_citation_docs
async def extract_document(
    user: AuthedUser,
    payload: ExtractDocumentPayload,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    extraction_client: AsyncExtractionClientDependency,
    docint_ds: DocIntDatasourceDependency,
    force: Annotated[bool, Query(description="Force re-extraction of the document.")] = False,
) -> ExtractJobResult:
    """Extract structured data from an existing document.

    Returns extracted data formatted according to the document's data model schema.
    """
    # This endpoint deviates from other endpoints because it uses a JSON payload so it
    # cannot accept a multipart/form-data request that includes a file.

    thread = await _get_thread_or_404(storage, user.user_id, payload.thread_id)

    request = await _resolve_extract_request(
        payload=payload,
        docint_ds=docint_ds,
        storage=storage,
        file_manager=file_manager,
        user=user,
    )
    # Set up cache for schema storage
    cache = ThreadFileCache[ExtractedDocument, ...](
        storage=storage,
        file_manager=file_manager,
        key_strategy=ExtractedDocumentKeyStrategy(),
        validate_fn=lambda cached, ctx: cached.system_prompt == ctx.get("system_prompt")
        and cached.extraction_config == ctx.get("extraction_config")
        and cached.extract_schema == ctx.get("extract_schema"),
    )

    # Try to get cached extracted document if not forcing regeneration
    if not force:
        cached_result = await cache.get(
            thread=thread,
            user_id=user.user_id,
            model_class=ExtractedDocument,
            file_ref=request.file_name,
            extract_schema=request.extraction_schema,
            system_prompt=request.extraction_system_prompt,
            extraction_config=request.extraction_config,
        )
        if cached_result:
            return ExtractJobResult(
                result=cached_result.result,
                job_id=cached_result.job_id,
                citations=cached_result.citations,
            )

    extract_response = await _upload_and_start_extract(
        request=request,
        user_id=user.user_id,
        file_manager=file_manager,
        extraction_client=extraction_client,
    )

    try:
        result = await extract_response.result(poll_interval=3.0)
        job_result = _create_job_result(result, extract_response.job_id)
        if not isinstance(job_result, ExtractJobResult):
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                message=f"Extract response is not a ExtractJobResult (was {type(job_result)})",
            )

        # Save the extracted document to cache
        extracted_document = ExtractedDocument(
            result=job_result.result,
            job_id=extract_response.job_id,
            extract_schema=request.extraction_schema,
            citations=job_result.citations,
            system_prompt=request.extraction_system_prompt,
            extraction_config=request.extraction_config,
        )
        await cache.set(
            thread=thread,
            user_id=user.user_id,
            data=extracted_document,
            file_ref=request.file_name,
            extract_schema=request.extraction_schema,
            system_prompt=request.extraction_system_prompt,
            extraction_config=request.extraction_config,
        )

        # Store the latest schema we used to extract the document
        schema_cache = ThreadFileCache[SchemaWithPrompt, ...](
            storage=storage,
            file_manager=file_manager,
            key_strategy=SchemaCacheKeyStrategy(),
        )
        await schema_cache.set(
            thread=thread,
            user_id=user.user_id,
            data=SchemaWithPrompt(extract_schema=request.extraction_schema),
            file_ref=request.file_name,
        )

        return job_result
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
@add_citation_docs
async def extract_document_async(
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
async def ingest_document(
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
