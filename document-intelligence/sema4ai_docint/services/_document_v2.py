import asyncio
import hashlib
import json
from pathlib import PurePath

from reducto.types import ParseResponse

from sema4ai_docint.models import ExtractionResult
from sema4ai_docint.models.document_v2 import DocumentV2
from sema4ai_docint.services._context import _DIContext
from sema4ai_docint.services.exceptions import DocumentServiceError
from sema4ai_docint.utils import compute_document_id


class _DocumentServiceV2:
    """Alpha version of DocumentService with breaking API changes.

    This service is intended to evolve the DocumentService with breaking changes
    while keeping the v1 API stable for existing users. When ready, this will
    become the default DocumentService.
    """

    def __init__(self, context: _DIContext) -> None:
        """Initialize the DocumentService V2 with shared context.

        Args:
            context: Shared DI context with access to external clients
        """
        self._context = context

    async def new_document(self, file_name: str) -> DocumentV2:
        """
        Create a Document object from a file that exists in Thread file storage.

        Args:
            file_name: The name of the file to create a Document object for.
            cached_path: The path to the file if it has already been localized.

        Raises:
            DocumentServiceError: If the file is not found

        Returns:
            A Document object.
        """
        transport = self._context.agent_server_transport
        from sema4ai_docint.agent_server_client.transport._utils import (
            call_transport_method_async,
        )

        assert transport is not None, "Agent server transport is required."
        normalized_file_name = PurePath(file_name).name
        try:
            local_path = await call_transport_method_async(
                transport, "get_file", normalized_file_name
            )
        except Exception as e:
            available_files_msg = ""
            if transport.thread_id:
                available_files = await call_transport_method_async(
                    transport, "list_file_refs", thread_id=transport.thread_id
                )
                available_files_msg = f" Available files: {available_files}"
            raise DocumentServiceError(
                f"File not found: {normalized_file_name}.{available_files_msg}"
            ) from e

        return DocumentV2(
            file_name=file_name,
            document_id=compute_document_id(local_path),
            local_file_path=local_path,
        )

    async def parse(
        self, document: DocumentV2, *, force_reload: bool = False, config: dict | None = None
    ) -> ParseResponse:
        from sema4ai_docint.services.persistence import DocumentOperationType

        assert self._context.extraction_service_async is not None, "Extraction service is required."
        assert self._context.persistence_service is not None, "Persistence service is required."
        assert self._context.agent_server_transport is not None, (
            "Agent server transport is required."
        )

        # Generate cache key for parse operation
        cache_key = self._context.persistence_service.cache_key_for(
            document.file_name, DocumentOperationType.PARSE
        )

        if not force_reload:
            cached = await self._context.persistence_service.load(cache_key)
            if cached is not None:
                return ParseResponse.model_validate_json(cached)

        reducto_id = await self._context.extraction_service_async.upload(
            await document.get_local_path(self._context.agent_server_transport)
        )
        response = await self._context.extraction_service_async.parse(reducto_id, config=config)
        await self._context.persistence_service.save(cache_key, response.model_dump_json().encode())

        return response

    async def get_schema(self, document: DocumentV2) -> dict | None:
        from sema4ai_docint.services.persistence import DocumentOperationType

        assert self._context.persistence_service is not None, "Persistence service is required."

        cache_key = self._context.persistence_service.cache_key_for(
            document.file_name, DocumentOperationType.SCHEMA
        )

        cached = await self._context.persistence_service.load(cache_key)
        if cached:
            return json.loads(cached)

        return None

    async def generate_schema(
        self,
        document: DocumentV2,
        *,
        force_reload: bool = False,
        model_schema: str | dict | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
        user_prompt: str | None = None,
    ) -> dict:
        """Generate a JSON Schema from a document by analyzing its structure and content.

        This method analyzes a document (PDF, DOCX, Excel, images, etc.) and generates a JSON Schema
        that describes the document's data structure.

        The generated schema is automatically cached in thread storage. Subsequent calls
        with the same file_name will return the cached result unless force_reload is True.

        Args:
            document: The document to generate a schema for
            force_reload: If True, bypass cache and re-generate the schema
            model_schema: Optional reference schema to guide the structure (JSON string or dict)
            start_page: Optional starting page for analysis (1-indexed, PDF/TIFF only)
            end_page: Optional ending page for analysis (1-indexed, PDF/TIFF only)
            user_prompt: Optional additional instructions for schema generation

        Returns:
            A dictionary containing the generated JSON Schema

        Raises:
            AssertionError: If required context dependencies are not available
        """
        from sema4ai_docint.services.persistence import DocumentOperationType

        assert self._context.agent_server_transport is not None, (
            "Agent server transport is required."
        )
        assert self._context.persistence_service is not None, "Persistence service is required."

        # Generate cache key for schema operation
        cache_key = self._context.persistence_service.cache_key_for(
            document.file_name, DocumentOperationType.SCHEMA
        )

        # Check cache first (unless force_reload)
        if not force_reload:
            cached = await self._context.persistence_service.load(cache_key)
            if cached is not None:
                return json.loads(cached)

        # Generate new schema using agent client in a thread to avoid blocking the event loop
        schema = await asyncio.to_thread(
            self._context.agent_client.generate_schema,
            document.file_name,
            model_schema=model_schema,
            start_page=start_page,
            end_page=end_page,
            user_prompt=user_prompt,
        )

        # Save to cache
        await self._context.persistence_service.save(cache_key, json.dumps(schema).encode())

        return schema

    async def extract_document(
        self,
        document: DocumentV2,
        extraction_schema: dict,
        *,
        force_reload: bool = False,
        extraction_config: dict | None = None,
        prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract structured data from a document using a JSON Schema.

        This method extracts data from a document according to a provided JSON Schema.
        If a persistence service is available, the extracted data is automatically cached.
        Subsequent calls with the same parameters will return the cached result unless
        force_reload is True.

        Args:
            document: The document to extract from
            extraction_schema: JSON Schema describing the desired output structure
            force_reload: If True, bypass cache and re-extract the data
            extraction_config: Optional advanced Reducto configuration
            prompt: Optional instructions to guide the extraction process
            start_page: Optional starting page for extraction (1-indexed)
            end_page: Optional ending page for extraction (1-indexed)

        Returns:
            A dictionary containing the extracted data matching the provided schema

        Raises:
            AssertionError: If required context dependencies are not available
        """
        from sema4ai_docint.services.persistence import DocumentOperationType

        assert self._context.extraction_service_async is not None, "Extraction service is required."
        assert self._context.agent_server_transport is not None, (
            "Agent server transport is required."
        )

        # Compute hash of extraction parameters for cache validation
        params_dict = {
            "extraction_schema": extraction_schema,
            "extraction_config": extraction_config,
            "start_page": start_page,
            "end_page": end_page,
            "thread_id": self._context.agent_server_transport.thread_id,
        }
        params_hash = hashlib.sha256(json.dumps(params_dict, sort_keys=True).encode()).hexdigest()

        if not force_reload and self._context.persistence_service:
            cache_key = self._context.persistence_service.cache_key_for(
                document.file_name, DocumentOperationType.EXTRACT
            )
            cached = await self._context.persistence_service.load(cache_key)
            if cached:
                cached_data = json.loads(cached)
                if cached_data.pop("params_hash", None) == params_hash:
                    return ExtractionResult(**cached_data)

        # Prepare extraction input - use local file path
        extraction_input = await document.get_local_path(self._context.agent_server_transport)

        # Perform extraction
        extract_response = await self._context.extraction_service_async.extract_with_schema(
            extraction_input=extraction_input,
            extraction_schema=extraction_schema,
            extraction_config=extraction_config,
            prompt=prompt,
            start_page=start_page,
            end_page=end_page,
        )

        if self._context.persistence_service:
            cache_key = self._context.persistence_service.cache_key_for(
                document.file_name, DocumentOperationType.EXTRACT
            )
            cache_entry = {
                "results": extract_response.results,
                "citations": extract_response.citations,
                "params_hash": params_hash,
            }
            await self._context.persistence_service.save(
                cache_key, json.dumps(cache_entry).encode()
            )

        return extract_response
