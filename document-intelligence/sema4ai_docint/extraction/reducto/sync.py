"""Synchronous wrapper around the async extraction client.

Deprecated:
    SyncExtractionClient is deprecated and will be removed in a future version.
    Use AsyncExtractionClient instead for better performance and resource efficiency.
"""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from aiofiles.threadpool.binary import AsyncBufferedReader
from reducto import AsyncReducto
from reducto.types import ExtractResponse, ParseResponse, SplitCategory, SplitResponse

from sema4ai_docint.models.extraction import ExtractionResult

from .async_ import AsyncExtractionClient
from .client import _BaseReductoClient

if TYPE_CHECKING:
    from .async_ import Job


class SyncExtractionClient(_BaseReductoClient):
    """Synchronous wrapper around AsyncExtractionClient.

    This client provides a synchronous interface by wrapping AsyncExtractionClient.
    All business logic is implemented in AsyncExtractionClient to avoid code duplication.

    Warning:
        Using this client creates a new event loop for each operation, which is inefficient.
        For better performance, use AsyncExtractionClient directly in an async context.

    Deprecated:
        This class is deprecated and will be removed in a future version.
        Use AsyncExtractionClient instead. The synchronous client wraps the async
        implementation and uses asyncio.run(), which is less efficient than using
        async directly.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        disable_ssl_verification: bool = False,
    ):
        """Initialize the sync client by wrapping an async client.

        Args:
            api_key: Sema4.ai API key.
            base_url: Optional base URL for the Reducto API.
            disable_ssl_verification: Whether to disable SSL verification.

        Deprecated:
            This class is deprecated. Use AsyncExtractionClient instead.
        """
        warnings.warn(
            "SyncExtractionClient is deprecated and will be removed in a future version. "
            "Use AsyncExtractionClient instead for better performance and resource efficiency.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Create the async client that does all the real work
        self._async_client = AsyncExtractionClient(
            api_key=api_key,
            base_url=base_url,
            disable_ssl_verification=disable_ssl_verification,
        )

        # Expose attributes for compatibility
        self.base_url = self._async_client.base_url
        self.disable_ssl_verification = self._async_client.disable_ssl_verification

    def _run_async(self, coro):
        """Run an async coroutine in a new event loop and clean up resources.

        This helper ensures that cached resources (like aiohttp sessions) tied to
        the event loop are properly closed after each operation, preventing
        "Event loop is closed" errors on subsequent calls.

        Args:
            coro: The coroutine to run.

        Returns:
            The result of the coroutine.
        """
        try:
            result = asyncio.run(coro)
            return result
        finally:
            # Close and clear the cached aiohttp session if it was created
            # This prevents it from being tied to a closed event loop
            if self._async_client._aiohttp_session is not None:
                # Run the close operation in a new event loop since the previous one is closed
                asyncio.run(self._async_client._aiohttp_session.close())
                self._async_client._aiohttp_session = None

    def upload(
        self,
        document: Path | bytes | BinaryIO | AsyncBufferedReader,
        *,
        content_length: int | None = None,
        chunk_size: int = 64 * 1024 * 1024,  # 64MB chunks for streaming
        progress_callback: Callable[[int, int], Any] | None = None,
    ) -> str:
        """Upload a document to Reducto synchronously.

        Args:
            document: A `Path` to a local file, raw `bytes`, or a binary file-like object to upload.
            content_length: Optional explicit content length. If not provided, it will be
                inferred when possible.

        Returns:
            The file ID of the uploaded document.
        """
        return self._run_async(self._async_client.upload(document, content_length=content_length))

    def unwrap(self) -> AsyncReducto:
        """Return the underlying Reducto client.

        Returns:
            The underlying Reducto client.

        Note:
            This returns the async client's underlying client for compatibility.
        """
        return self._async_client.unwrap()

    def parse(self, document_id: str, config: dict[str, Any] | None = None) -> ParseResponse:
        """Parse a document using Reducto synchronously.

        Args:
            document_id: The Reducto file ID of the document to parse. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            config: Optional configuration to override default parse settings

        Returns:
            The parse response from Reducto.
        """
        return self._run_async(self._async_client.parse(document_id, config))

    def split(
        self,
        document_id: str,
        split_description: Iterable[SplitCategory],
        split_rules: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> SplitResponse:
        """Split a document using Reducto synchronously.

        Args:
            document_id: The Reducto file ID of the document to split. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            split_description: The description of the split to perform.
            split_rules: Optional split rules to use.
            config: Optional configuration to override default split settings

        Returns:
            The split response from Reducto.
        """
        return self._run_async(
            self._async_client.split(document_id, split_description, split_rules, config)
        )

    def extract(
        self,
        document_id: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
        extraction_config: dict[str, Any] | None = None,
    ) -> ExtractResponse:
        """Extract data from a document using Reducto synchronously.

        Args:
            document_id: The Reducto file ID of the document to extract data from. Can also
                be a job ID in the format `jobid://{job_id}` to reference the output of a
                previous job.
            schema: The JSON schema for extraction
            system_prompt: Optional custom system prompt for extraction
            start_page: Optional start page for extraction
            end_page: Optional end page for extraction
            extraction_config: Optional configuration to override default extraction settings

        Returns:
            The extraction response from Reducto.
        """
        return self._run_async(
            self._async_client.extract(
                document_id, schema, system_prompt, start_page, end_page, extraction_config
            )
        )

    def extract_with_schema(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any] | str,
        extraction_config: dict[str, Any] | None = None,
        prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract data from a document using Reducto synchronously.

        Note: citations are enabled by default, to disable them, provide an extraction_config
        with generate_citations set to False.

        Args:
            extraction_input: The path to a local file, a Reducto job ID,
                or a Job handle (passed through to async client).
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            extraction_config: Optional extraction configuration for processing
            prompt: Optional system prompt for Reducto
            start_page: Optional start page for extraction
            end_page: Optional end page for extraction

        Returns:
            The extraction response from Reducto.
        """
        if isinstance(extraction_schema, str):
            import json

            _schema = json.loads(extraction_schema)
        else:
            _schema = extraction_schema

        return self._run_async(
            self._async_client.extract_with_schema(
                extraction_input, _schema, extraction_config, prompt, start_page, end_page
            )
        )

    def extract_with_data_model(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any] | str,
        data_model_prompt: str | None = None,
        extraction_config: dict[str, Any] | None = None,
        document_layout_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract data from a document using Reducto synchronously.

        Note: citations are enabled by default, to disable them, provide an extraction_config
        with generate_citations set to False.

        Args:
            extraction_input: The path to a local file, a Reducto job ID
                or a Job handle (passed through to async client).
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            data_model_prompt: Optional system prompt for processing
            extraction_config: Optional extraction configuration for processing
            document_layout_prompt: Optional system prompt for layout processing
            start_page: Optional start page for extraction (1-indexed)
            end_page: Optional end page for extraction (1-indexed)

        Returns:
            An ExtractionResult containing the extracted data and citations.
        """
        return self._run_async(
            self._async_client.extract_with_data_model(
                extraction_input,
                extraction_schema,
                data_model_prompt,
                extraction_config,
                document_layout_prompt,
                start_page,
                end_page,
            )
        )

    def extract_details(
        self,
        file_path: Path,
        extraction_schema: str | dict[str, Any],
        data_model_prompt: str | None = None,
        extraction_config: dict[str, Any] | None = None,
        document_layout_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract data from a document using Reducto, returning an ExtractionResult.

        Note: This method is deprecated in favor of extract_with_data_model.

        Args:
            file_path: The path to the document file to extract from.
            extraction_schema: JSONSchema as a string or dictionary to direct extraction.
            data_model_prompt: Optional system prompt for the data model.
            extraction_config: Optional Reducto extraction configuration for processing.
            document_layout_prompt: Optional system prompt for document layout.
            start_page: Optional start page for extraction (1-indexed).
            end_page: Optional end page for extraction (1-indexed).
        """
        warnings.warn(
            "extract_details is deprecated in favor of extract_with_data_model.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.extract_with_data_model(
            file_path,
            extraction_schema,
            data_model_prompt,
            extraction_config,
            document_layout_prompt,
            start_page,
            end_page,
        )
