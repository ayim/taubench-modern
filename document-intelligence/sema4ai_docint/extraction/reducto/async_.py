"""Asynchronous client for document extraction using Reducto."""

from __future__ import annotations

import asyncio
import json
import warnings
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, cast

import aiofiles
import aiofiles.os
import aiohttp
import httpx
from reducto import AsyncReducto
from reducto.types import ExtractResponse, ParseResponse, SplitCategory, SplitResponse
from reducto.types.job_get_response import Result

from sema4ai_docint.logging import logger
from sema4ai_docint.models.extraction import ExtractionResult

if TYPE_CHECKING:
    # Type hints for async file objects when aiofiles is available
    from aiofiles.threadpool.binary import AsyncBufferedReader

from .client import _BaseReductoClient
from .exceptions import (
    JobFailedError,
    UploadForbiddenError,
    UploadMissingFileIdError,
    UploadMissingPresignedUrlError,
    UploadPresignRequestError,
    UploadPutError,
)


class JobType(StrEnum):
    """Types of jobs that can be submitted for async processing."""

    PARSE = "parse"
    EXTRACT = "extract"
    SPLIT = "split"


class JobStatus(StrEnum):
    """Status of a job submitted to Reducto for processing."""

    # Matches Reducto's types.job_get_response.JobGetResponse.status which is a Literal

    PENDING = "Pending"
    COMPLETED = "Completed"
    FAILED = "Failed"
    IDLE = "Idle"


@dataclass
class Job:
    """Represents a job submitted to Reducto for processing."""

    job_id: str
    job_type: JobType
    client: AsyncExtractionClient

    async def status(self) -> JobStatus:
        """Get the current status of this job."""
        status = await self.client.get_job_status(self.job_id)
        return JobStatus(status)

    async def wait(self, poll_interval: float = 3.0) -> Result:
        """Wait for this job to complete and return the result.

        Args:
            poll_interval: Time in seconds between poll attempts.

        Returns:
            The job result.
        """
        return await self.client.wait_for_job(self.job_id, poll_interval)

    async def result(
        self, poll_interval: float = 3.0
    ) -> ParseResponse | ExtractResponse | SplitResponse:
        """Wait for this job to complete and return the typed result."""
        raw_result = await self.wait(poll_interval)

        if self.job_type == "parse":
            parsed_resp = cast(ParseResponse, raw_result)
            return self.client.localize_parse_response(parsed_resp)
        elif self.job_type == "extract":
            return cast(ExtractResponse, raw_result)
        elif self.job_type == "split":
            return cast(SplitResponse, raw_result)
        else:
            raise ValueError(f"Unknown job type: {self.job_type}")


class AsyncExtractionClient(_BaseReductoClient):
    """Asynchronous Client for extracting documents using Reducto.

    This implementation uses the asynchronous Reducto client to upload and process documents.
    It leverages the Job API to handle long-running operations asynchronously.

    Features:
        - Streaming uploads with aiohttp
        - Job-based API for non-blocking operations
        - Progress tracking for large file uploads
        - Automatic session management for connection pooling
        - Enterprise network support (SSL/proxy configurations)

    The client maintains an aiohttp session for efficient connection reuse across
    multiple uploads. Remember to close the client when done to clean up resources.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        disable_ssl_verification: bool = False,
    ):
        """Initialize the async Reducto client.

        Args:
            api_key: Sema4.ai API key.
            base_url: Optional base URL for the Reducto API.
            disable_ssl_verification: Whether to disable SSL verification.
        """
        if not base_url:
            base_url = _BaseReductoClient.SEMA4_REDUCTO_ENDPOINT

        # Normalize base_url before storing and passing to client
        # This ensures consistent URL construction (e.g., f"{self.base_url}/upload")
        self.base_url = self._normalize_base_url(base_url)

        self.client = AsyncExtractionClient._new_async_reducto_client(
            api_key,
            base_url=self.base_url,
            disable_ssl_verification=disable_ssl_verification,
        )
        self.disable_ssl_verification = disable_ssl_verification

        # Initialize aiohttp session for streaming uploads (lazy initialization)
        self._aiohttp_session: aiohttp.ClientSession | None = None

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str:
        """Normalize base_url by removing trailing slashes.

        This ensures consistent URL construction when appending paths like "/upload"
        to avoid double slashes (e.g., "https://backend.sema4.ai/reducto//upload").

        Args:
            base_url: The base URL to normalize, or None to use the default endpoint.

        Returns:
            The normalized base URL without trailing slashes, or the default endpoint if None.
        """
        if not base_url:
            return _BaseReductoClient.SEMA4_REDUCTO_ENDPOINT
        return base_url.rstrip("/")

    @classmethod
    def _new_async_reducto_client(
        cls,
        api_key: str,
        base_url: str,
        disable_ssl_verification: bool = False,
    ) -> AsyncReducto:
        """Create a new async Reducto client."""
        from ssl import SSLContext

        import sema4ai_http

        network_config = sema4ai_http.get_network_profile()
        ssl_context: SSLContext | None | bool = network_config.ssl_context
        if disable_ssl_verification:
            ssl_context = False
        elif ssl_context is None:
            raise ValueError("SSL context missing from sema4ai-http-helper NetworkProfile")

        # Set up mounts for proxy configuration
        mounts = cls._make_mounts(network_config)

        # Create httpx async client with the configured mounts and SSL context
        httpx_client = httpx.AsyncClient(mounts=mounts, verify=ssl_context)

        rc = AsyncReducto(
            api_key="unused",  # We have to set a Reducto api_key here, but it's ignored
            # in usage of the client.
            base_url=base_url,
            http_client=httpx_client,
        )
        rc._client.headers["X-API-Key"] = api_key
        return rc

    async def upload(  # noqa: C901
        self,
        document: Path | bytes | BinaryIO | AsyncBufferedReader,
        *,
        content_length: int | None = None,
        chunk_size: int = 64 * 1024 * 1024,  # 64MB chunks for streaming
        progress_callback: Callable[[int, int], Any] | None = None,
    ) -> str:
        """Upload a document to Reducto asynchronously with streaming support.

        This unified method handles files of any size (up to 5GB) efficiently using:
        - True streaming with aiohttp when available
        - Chunked reading with progress tracking
        - Automatic file size detection
        - Memory-efficient processing for large files

        Args:
            document: A `Path` to a local file, raw `bytes`, a binary file-like object,
                     or an async file object (from aiofiles) to upload.
            content_length: Optional explicit content length. If not provided, it will be inferred.
            chunk_size: Size of chunks for streaming uploads (default 64MB).
            progress_callback: Optional callback for progress updates. Called with
                (bytes_uploaded, total_bytes).

        Returns:
            The file ID of the uploaded document.

        Notes:
            - Maximum file size: 5GB (Reducto's presigned URL limit)
            - Respects enterprise network configurations via sema4ai_http

        Example:
            ```python
            # Upload any size file
            file_id = await client.upload(Path("document.pdf"))

            # With progress tracking for large files
            async def on_progress(uploaded: int, total: int):
                percent = (uploaded / total) * 100
                print(f"Upload progress: {percent:.1f}%")

            file_id = await client.upload(
                Path("large_document.pdf"),
                progress_callback=on_progress
            )

            # With async file (requires aiofiles)
            async with aiofiles.open("document.pdf", "rb") as f:
                file_id = await client.upload(f)

            # With bytes
            file_id = await client.upload(pdf_bytes)
            ```
        """
        # Step 1: Request presigned URL
        try:
            upload_resp = await self.client._client.post(
                f"{self.base_url}/upload",
                headers=self.client._client.headers,
            )
        except httpx.HTTPError as exc:
            logger.error(f"Presign request failed: {exc}")
            raise UploadPresignRequestError(
                "Failed to request presigned upload URL.",
            ) from exc

        # Handle errors
        if upload_resp.status_code == HTTPStatus.FORBIDDEN:
            logger.error(f"File upload failed with http/403: {upload_resp}")
            raise UploadForbiddenError(
                "File upload forbidden (HTTP 403). Check your Sema4.ai API key and permissions."
            )

        try:
            upload_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.error(f"Presign request returned error status: {status}")
            raise UploadPresignRequestError(
                "Failed to request presigned upload URL.", status_code=status
            ) from exc

        try:
            resp = upload_resp.json()
        except Exception as exc:
            logger.error(f"Invalid presign response: {exc}")
            raise UploadPresignRequestError("Failed to parse presign response.") from exc

        # Validate response
        if "presigned_url" not in resp:
            logger.error(f"File upload failed: No presigned URL returned. Response: {upload_resp}")
            raise UploadMissingPresignedUrlError("File upload failed: No presigned URL returned.")
        if "file_id" not in resp:
            logger.error(f"File upload failed: No file ID returned. Response: {upload_resp}")
            raise UploadMissingFileIdError("File upload failed: No file ID returned.")

        # Step 2: Prepare for upload - determine file size and create data source
        presigned_url = resp["presigned_url"]
        file_id = resp["file_id"]

        # Determine content length
        if content_length is None:
            if isinstance(document, Path):
                # Get file size
                stat = await aiofiles.os.stat(document)
                content_length = stat.st_size
            elif isinstance(document, bytes):
                content_length = len(document)
            # For file objects, try to determine size
            elif hasattr(document, "seek") and hasattr(document, "tell"):
                current_pos = document.tell()
                document.seek(0, 2)  # Seek to end
                content_length = document.tell()
                document.seek(current_pos)  # Return to original position

        # Step 3: Upload using aiohttp for all upload types
        await self._upload_with_aiohttp(
            presigned_url, document, content_length, chunk_size, progress_callback
        )

        return file_id

    def _create_aiohttp_session_sync(self) -> aiohttp.ClientSession:
        """Create an aiohttp session with network profile from sema4ai_http (sync
        version for __init__)."""

        import ssl

        import sema4ai_http

        network_config = sema4ai_http.get_network_profile()

        # Create connector with SSL context
        connector_kwargs = {}
        if network_config.ssl_context:
            if isinstance(network_config.ssl_context, ssl.SSLContext):
                connector_kwargs["ssl"] = network_config.ssl_context
            elif network_config.ssl_context is False:
                connector_kwargs["ssl"] = False

        # Handle proxy configuration
        # Note: aiohttp handles proxies differently than httpx
        # We'll need to pass proxy to session.request() calls
        proxy = None
        if network_config.proxy_config.https:
            proxy = (
                network_config.proxy_config.https[0] if network_config.proxy_config.https else None
            )
        elif network_config.proxy_config.http:
            proxy = (
                network_config.proxy_config.http[0] if network_config.proxy_config.http else None
            )

        connector = aiohttp.TCPConnector(**connector_kwargs)  # type: ignore
        session = aiohttp.ClientSession(connector=connector)

        # Store proxy for later use
        session._proxy = proxy  # type: ignore

        return session

    # : Fix lint issues in this function
    async def _upload_with_aiohttp(  # noqa: C901
        self,
        presigned_url: str,
        document: Path | bytes | BinaryIO | Any,
        content_length: int | None,
        chunk_size: int,
        progress_callback: Callable[[int, int], Any] | None,
    ) -> None:
        """Upload using aiohttp for all document types with streaming support when applicable."""

        async def stream_generator() -> AsyncIterator[bytes]:  # noqa: C901
            """Generate chunks from the document source."""
            bytes_read = 0

            if isinstance(document, bytes):
                # Handle bytes directly
                if progress_callback and content_length:
                    await progress_callback(len(document), content_length)
                yield document
            elif isinstance(document, Path):
                # Stream from file
                async with aiofiles.open(document, "rb") as f:
                    while True:
                        chunk = await f.read(chunk_size)
                        if not chunk:
                            break
                        bytes_read += len(chunk)
                        if progress_callback and content_length:
                            await progress_callback(bytes_read, content_length)
                        yield chunk

            elif hasattr(document, "read"):
                # Stream from file-like object
                is_async = asyncio.iscoroutinefunction(document.read)

                while True:
                    if is_async:
                        chunk = await document.read(chunk_size)  # type: ignore
                    else:
                        chunk = await asyncio.to_thread(document.read, chunk_size)

                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    if progress_callback and content_length:
                        await progress_callback(bytes_read, content_length)
                    yield chunk

        # Get or create aiohttp session with network profile
        session = self.aiohttp_session

        headers = {}
        if content_length:
            headers["Content-Length"] = str(content_length)

        logger.debug("Uploading to presigned URL using aiohttp")

        # Get proxy from session if set
        proxy = getattr(session, "_proxy", None)

        async with session.put(
            presigned_url,
            data=stream_generator(),
            headers=headers,
            proxy=proxy,
            # Skip content-type as Reducto docs specifically indicate it should be skipped
            # see https://docs.reducto.ai/recipes/presigned-url-upload-method async implementation
            skip_auto_headers=["content-type"],
        ) as response:
            if response.status >= HTTPStatus.BAD_REQUEST:
                text = await response.text()
                logger.error(f"Upload failed with status {response.status}: {text}")
                raise UploadPutError(
                    "Failed to upload content to presigned URL.",
                    status_code=response.status,
                )

    def unwrap(self) -> AsyncReducto:
        """Return the underlying async Reducto client.

        Returns:
            The underlying async Reducto client.
        """
        return self.client

    @property
    def aiohttp_session(self) -> aiohttp.ClientSession:
        """Get the aiohttp session used for streaming uploads.

        Returns:
            The aiohttp ClientSession.

        Note:
            This session is managed by the client and will be closed when
            the client is closed. Do not close it manually.
        """
        if self._aiohttp_session is None:
            self._aiohttp_session = self._create_aiohttp_session_sync()
        return self._aiohttp_session

    # ============================================================================
    # Job Management Methods - For true async operation
    # ============================================================================

    async def get_job_status(self, job_id: str) -> str:
        """Get the current status of a job without waiting for completion.

        Args:
            job_id: The ID of the job to check.

        Returns:
            The job status: "Pending", "Idle", "Completed", "Failed", etc.
        """
        job_resp = await self.client.job.get(job_id=job_id)
        return job_resp.status

    async def wait_for_job(self, job_id: str, poll_interval: float = 3.0) -> Result:
        """Wait for a job to complete and return the raw result.

        This is a lower-level method that returns the raw Result object.
        Use the Job.result() method for typed results.

        Args:
            job_id: The ID of the job to wait for.
            poll_interval: Time in seconds between poll attempts.

        Returns:
            The raw job result.

        Raises:
            JobFailedError: If the job fails.
        """
        return await self._complete(job_id, poll_interval)

    # ============================================================================
    # Non-blocking Job Submission Methods - Returns immediately with Job handle
    # ============================================================================

    async def start_parse(self, document_id: str, config: dict | None = None) -> Job:
        """Start a parse job and return immediately with a Job handle.

        This method returns immediately after submitting the job, allowing you to:
        - Start multiple jobs concurrently
        - Check job status later
        - Wait for completion when needed

        Args:
            document_id: The Reducto file ID of the document to parse. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            config: Optional configuration to override default parse settings

        Returns:
            A Job handle that can be used to track and retrieve results.

        Example:
            ```python
            # Start multiple parse jobs concurrently
            job1 = await client.start_parse(doc1_id)
            job2 = await client.start_parse(doc2_id)

            # Do other work while jobs are processing...

            # Later, wait for results
            result1 = await job1.result()
            result2 = await job2.result()
            ```
        """
        opts = self.parse_opts(config)

        if opts:
            import pprint

            logger.info(f"Parse config: {pprint.pformat(opts, indent=2)}")

        job_resp = await self.client.parse.run_job(
            document_url=document_id,
            **opts,
        )

        return Job(job_id=job_resp.job_id, job_type=JobType.PARSE, client=self)

    async def start_parse_file(self, file: Path | str, config: dict | None = None) -> Job:
        """Start a parse job for a file at the provided path and return immediately
        with a Job handle.

        Args:
            file: The path to the file to parse.
            config: Optional configuration to override default parse settings

        Returns:
            A Job handle that can be used to track and retrieve results.
        """
        file_id = await self.upload(file)
        return await self.start_parse(file_id, config)

    async def start_split(
        self,
        document_id: str,
        split_description: Iterable[SplitCategory],
        split_rules: str | None = None,
        config: dict | None = None,
    ) -> Job:
        """Start a split job and return immediately with a Job handle.

        Args:
            document_id: The Reducto file ID of the document to split. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            split_description: The description of the split to perform.
            split_rules: Optional split rules to use.
            config: Optional configuration to override default split settings

        Returns:
            A Job handle that can be used to track and retrieve results.
        """
        opts = self.split_opts(config)
        opts["split_description"] = list(split_description)
        if split_rules:
            opts["split_rules"] = split_rules

        if opts:
            import pprint

            logger.info(f"Split config: {pprint.pformat(opts, indent=2)}")

        job_resp = await self.client.split.run_job(
            document_url=document_id,
            **opts,
        )

        return Job(job_id=job_resp.job_id, job_type=JobType.SPLIT, client=self)

    async def start_extract(
        self,
        document_id: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
        extraction_config: dict | None = None,
    ) -> Job:
        """Start an extraction job and return immediately with a Job handle.

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
            A Job handle that can be used to track and retrieve results.

        Example:
            ```python
            # Start multiple extraction jobs with different schemas
            jobs = []
            for schema in schemas:
                job = await client.start_extract(doc_id, schema)
                jobs.append(job)

            # Wait for all jobs to complete
            results = await asyncio.gather(*[job.result() for job in jobs])
            ```
        """
        if system_prompt:
            logger.info(f"using custom prompt for extraction: '{system_prompt}'")
        else:
            logger.info("using standard prompt for extraction")

        opts = self.extract_opts(
            schema,
            (
                _BaseReductoClient.DEFAULT_EXTRACT_SYSTEM_PROMPT
                if system_prompt is None
                else system_prompt
            ),
            start_page=start_page,
            end_page=end_page,
            extraction_config=extraction_config,
        )

        if opts:
            import pprint

            logger.info(f"Extraction config: {pprint.pformat(opts, indent=2)}")

        agent_extract = opts.pop("agent_extract", {"enabled": False})

        extra_body = {}
        if agent_extract["enabled"]:
            extra_body["agent_extract"] = agent_extract

        job_resp = await self.client.extract.run_job(
            document_url=document_id,
            **opts,
            extra_body=extra_body,
        )

        return Job(job_id=job_resp.job_id, job_type=JobType.EXTRACT, client=self)

    # ============================================================================
    # Convenience Methods - Submit job and wait for completion
    # ============================================================================

    async def parse(self, document_id: str, config: dict | None = None) -> ParseResponse:
        """Parse a document using Reducto asynchronously (convenience method).

        **Note**: This is a convenience method that submits the job and waits for completion.
        For true async operation where you don't want to block, use `start_parse()` instead.

        Args:
            document_id: The Reducto file ID of the document to parse. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            config: Optional configuration to override default parse settings

        Returns:
            The parse response from Reducto.

        Example:
            ```python
            # Convenience method - waits for completion
            result = await client.parse(doc_id)

            # For non-blocking operation, use start_parse instead:
            job = await client.start_parse(doc_id)
            # ... do other work ...
            result = await job.result()
            ```
        """
        job = await self.start_parse(document_id, config)
        res = await job.result()
        return cast(ParseResponse, res)

    async def split(
        self,
        document_id: str,
        split_description: Iterable[SplitCategory],
        split_rules: str | None = None,
        config: dict | None = None,
    ) -> SplitResponse:
        """Split a document using Reducto asynchronously (convenience method).

        **Note**: This is a convenience method that submits the job and waits for completion.
        For true async operation where you don't want to block, use `start_split()` instead.

        Args:
            document_id: The Reducto file ID of the document to split. Can also be a job ID
                in the format `jobid://{job_id}` to reference the output of a previous job.
            split_description: The description of the split to perform.
            split_rules: Optional split rules to use.
            config: Optional configuration to override default split settings

        Returns:
            The split response from Reducto.
        """
        job = await self.start_split(document_id, split_description, split_rules, config)
        res = await job.result()
        return cast(SplitResponse, res)

    async def extract(
        self,
        document_id: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
        extraction_config: dict | None = None,
    ) -> ExtractResponse:
        """Extract data from a document using Reducto asynchronously (convenience method).

        **Note**: This is a convenience method that submits the job and waits for completion.
        For true async operation where you don't want to block, use `start_extract()` instead.

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

        Example:
            ```python
            # Convenience method - waits for completion
            result = await client.extract(doc_id, schema)

            # For non-blocking operation with multiple schemas:
            jobs = [await client.start_extract(doc_id, s) for s in schemas]
            results = await asyncio.gather(*[job.result() for job in jobs])
            ```
        """
        job = await self.start_extract(
            document_id, schema, system_prompt, start_page, end_page, extraction_config
        )
        res = await job.result()
        return cast(ExtractResponse, res)

    async def _resolve_extraction_input(
        self, extraction_input: Path | str | Job, extraction_config: dict[str, Any] | None = None
    ) -> Job:
        """Resolve various extraction input types into a Job.

        Args:
            extraction_input: Can be:
                - Path: Local file path (will be uploaded)
                - str: Local file path (will be uploaded if exists), Reducto file ID,
                       or jobid:// URL to reference a previous job
                - Job: Existing Job object
            extraction_config: Optional configuration for parse operation

        Returns:
            A Job object that can be used for extraction

        Note:
            If you want to reference an existing job, use the format `jobid://{job_id}`.
            Strings that are not valid local file paths are treated as file IDs.
        """
        match extraction_input:
            case Path():
                file_id = await self.upload(extraction_input)
                return await self.start_parse(file_id, config=extraction_config)
            case str():
                # Check if string is a local file path
                path = Path(extraction_input)
                if path.exists():
                    # Upload the local file
                    file_id = await self.upload(path)
                    return await self.start_parse(file_id, config=extraction_config)
                elif extraction_input.startswith("jobid://"):
                    # Extract job_id from jobid:// URL and return Job directly
                    # This avoids creating a new parse job for an existing job reference
                    job_id = extraction_input.split("://")[1]
                    return Job(job_id=job_id, job_type=JobType.PARSE, client=self)
                else:
                    # Treat string as file ID and start a new parse job
                    return await self.start_parse(extraction_input, config=extraction_config)
            case Job():
                return extraction_input
            case _:
                raise ValueError(f"Invalid input type: {type(extraction_input)}")

    def _parse_extraction_schema(self, extraction_schema: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(extraction_schema, str):
            return json.loads(extraction_schema)
        else:
            return extraction_schema

    async def start_extract_with_schema(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any] | str,
        extraction_config: dict[str, Any] | None = None,
        prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> Job:
        """Start extracting data from a document using Reducto, returning a Job handle.

        Args:
            extraction_input: The path to a local file, a Reducto job ID, a Reducto file ID,
                or a Job handle.
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            extraction_config: Optional extraction configuration for processing
            prompt: Optional system prompt for Reducto
            start_page: Optional start page for extraction
            end_page: Optional end page for extraction
        """
        parsed_schema = self._parse_extraction_schema(extraction_schema)

        job = await self._resolve_extraction_input(extraction_input, extraction_config)

        # Append the user's prompt to our default system prompt if one was given
        system_prompt = _BaseReductoClient.DEFAULT_EXTRACT_SYSTEM_PROMPT
        if prompt:
            system_prompt = system_prompt + "\n" + prompt
        logger.info(f"System prompt: {system_prompt}")

        # We must wait for the parse to complete
        await job.wait()

        # Extract content with optional configuration
        return await self.start_extract(
            f"jobid://{job.job_id}",
            parsed_schema,
            extraction_config=extraction_config,
            system_prompt=system_prompt,
            start_page=start_page,
            end_page=end_page,
        )

    async def extract_with_schema(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any],
        extraction_config: dict[str, Any] | None = None,
        prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract data from a document using Reducto.

        Note: citations are enabled by default, to disable them, provide an extraction_config
        with generate_citations set to False.

        Args:
            extraction_input: The path to a local file, a Reducto job ID,
                or a Job handle.
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            extraction_config: Optional extraction configuration for processing
            prompt: Optional system prompt for Reducto
            start_page: Optional start page for extraction
            end_page: Optional end page for extraction
        """
        parsed_schema = self._parse_extraction_schema(extraction_schema)

        job = await self.start_extract_with_schema(
            extraction_input, parsed_schema, extraction_config, prompt, start_page, end_page
        )
        result = await job.result()
        extract_result = cast(ExtractResponse, result)
        return self.convert_extract_response(extract_result, prompt)

    async def start_extract_with_data_model(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any] | str,
        data_model_prompt: str | None = None,
        extraction_config: dict[str, Any] | None = None,
        document_layout_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> Job:
        """Start extracting data from a document using Reducto, returning a Job handle.

        Note: citations are enabled by default, to disable them, provide an extraction_config
        with generate_citations set to False.

        Args:
            extraction_input: The path to a local file, a Reducto job ID,
                or a Job handle.
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            data_model_prompt: Optional system prompt for processing
            extraction_config: Optional extraction configuration for processing
            document_layout_prompt: Optional system prompt for layout processing
            start_page: Optional start page for extraction (1-indexed)
            end_page: Optional end page for extraction (1-indexed)
        """
        parsed_schema = self._parse_extraction_schema(extraction_schema)

        job = await self._resolve_extraction_input(extraction_input, extraction_config)

        # Extract content using the schema
        system_prompt = _BaseReductoClient.DEFAULT_EXTRACT_SYSTEM_PROMPT
        if data_model_prompt:
            system_prompt += "\n" + data_model_prompt
        if document_layout_prompt:
            system_prompt += "\n" + document_layout_prompt
        logger.info(f"System prompt: {system_prompt}")

        # Wait for the parse to complete
        await job.wait()

        # Extract content with optional configuration
        return await self.start_extract(
            f"jobid://{job.job_id}",
            parsed_schema,
            system_prompt=system_prompt,
            start_page=start_page,
            end_page=end_page,
            extraction_config=extraction_config,
        )

    async def extract_with_data_model(
        self,
        extraction_input: Path | str | Job,
        extraction_schema: dict[str, Any] | str,
        data_model_prompt: str | None = None,
        extraction_config: dict[str, Any] | None = None,
        document_layout_prompt: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractionResult:
        """Extract data from a document using Reducto, returning an ExtractionResult.

        Note: citations are enabled by default, to disable them, provide an extraction_config
        with generate_citations set to False.

        Args:
            extraction_input: The path to a local file, a Reducto job ID,
                or a Job handle.
            extraction_schema: Extraction schema to use for processing (string or
                ExtractionSchema dict).
                This defines the structure for extracting data from the document.
                Should contain JSONSchema properties like 'type', 'properties', 'required'.
            data_model_prompt: Optional system prompt for processing
            extraction_config: Optional extraction configuration for processing
            document_layout_prompt: Optional system prompt for layout processing
            start_page: Optional start page for extraction (1-indexed)
            end_page: Optional end page for extraction (1-indexed)
        """
        parsed_schema = self._parse_extraction_schema(extraction_schema)
        job = await self.start_extract_with_data_model(
            extraction_input,
            parsed_schema,
            data_model_prompt,
            extraction_config,
            document_layout_prompt,
            start_page,
            end_page,
        )
        result = await job.result()

        # Get the extracted results
        logger.info("Content extracted successfully")
        extract_result = cast(ExtractResponse, result)
        return self.convert_extract_response(extract_result, data_model_prompt)

    async def extract_details(
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
        return await self.extract_with_data_model(
            file_path,
            extraction_schema,
            data_model_prompt,
            extraction_config,
            document_layout_prompt,
            start_page,
            end_page,
        )

    async def _complete(self, job_id: str, poll_interval: float = 3.0) -> Result:
        """Poll for job completion asynchronously.

        Args:
            job_id: The ID of the job to wait for.
            poll_interval: Time in seconds between poll attempts.

        Returns:
            The job result.

        Raises:
            JobFailedError: If the job fails.
        """
        while True:
            job_resp = await self.client.job.get(job_id=job_id)

            match job_resp.status:
                case "Completed":
                    return job_resp.result
                case "Failed":
                    raise JobFailedError(
                        reason=job_resp.reason or "Unknown job failure",
                        job_id=job_id,
                    )
                case "Pending" | "Idle":
                    await asyncio.sleep(poll_interval)
                case _:
                    raise Exception(f"Unknown job status: {job_resp.status}")

    async def close(self):
        """Close the underlying aiohttp and Reducto clients.

        This client will *not* be usable after this call.
        """
        # Close aiohttp session if it was created
        if self._aiohttp_session is not None:
            await self._aiohttp_session.close()

        # Close the Reducto client
        await self.client.close()

    def is_closed(self) -> bool:
        """Check if either client is closed."""
        if self._aiohttp_session is not None:
            return self._aiohttp_session.closed
        return self.client.is_closed()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close the client and aiohttp session."""
        await self.close()
