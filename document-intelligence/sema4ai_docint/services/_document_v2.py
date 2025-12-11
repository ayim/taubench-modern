import asyncio
import json
from pathlib import PurePath

from reducto.types import ParseResponse
from sema4ai.actions.chat import list_files

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
        assert self._context.agent_server_transport is not None, (
            "Agent server transport is required."
        )
        normalized_file_name = PurePath(file_name).name
        try:
            local_path = self._context.agent_server_transport.get_file(normalized_file_name)
        except Exception as e:
            raise DocumentServiceError(
                f"File not found: {normalized_file_name}. Available files: {list_files()}"
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
            document.get_local_path(self._context.agent_server_transport)
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
