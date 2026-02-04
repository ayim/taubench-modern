"""Schema validation and transformation service.

This module provides a Protocol-based service for validating and transforming
data against schemas. The Protocol design allows easy mocking/overriding for testing.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from reducto.types.job_get_response import Result
from sema4ai_docint.extraction.reducto.async_ import JobStatus, JobType

if TYPE_CHECKING:
    from sema4ai_docint.extraction.reducto.async_ import (
        AsyncExtractionClient,
        Job,
    )

    from agent_platform.core.semantic_data_model.schemas import (
        JsonData,
        Schema,
        SchemaData,
        Transformation,
        Validation,
    )


class SchemaServiceProtocol(Protocol):
    """Protocol for schema validation and transformation operations.

    This protocol defines the interface for schema operations, allowing
    different implementations for production vs testing.
    """

    def create_schema_data(self, data: JsonData) -> SchemaData:
        """Create a new SchemaData from raw JSON data with empty lineage.

        Args:
            data: Raw JSON data (object or array)

        Returns:
            SchemaData with empty lineage history
        """
        ...

    def validate(self, schema_data: SchemaData, schema: Schema) -> SchemaData:
        """Validate data against all validation rules in a schema.

        Returns a new SchemaData with the validation recorded in lineage.

        Args:
            schema_data: The SchemaData containing data and existing lineage
            schema: The Schema containing validation rules

        Returns:
            New SchemaData with validation event appended to history
        """
        ...

    def transform(
        self,
        schema_data: SchemaData,
        transformation: Transformation,
        source_schema: Schema,
        target_schema: Schema,
    ) -> SchemaData:
        """Transform data from source schema to target schema.

        Checks if transformed data conforms to target schema shape.
        Records the transformation in lineage.

        Args:
            schema_data: The SchemaData containing data and existing lineage
            transformation: The Transformation containing the JQ transformation
            source_schema: The source Schema
            target_schema: The target Schema to check conformance against

        Returns:
            New SchemaData with transformed data and updated lineage
        """
        ...


class SchemaService:
    """Default implementation of SchemaServiceProtocol.

    Provides schema validation and transformation operations. Subclass and override
    the protected methods to customize behavior (e.g., for testing).
    """

    def create_schema_data(self, data: JsonData) -> SchemaData:
        """Create a new SchemaData from raw JSON data with empty lineage.

        Args:
            data: Raw JSON data (object or array)

        Returns:
            SchemaData with empty lineage history
        """
        from agent_platform.core.semantic_data_model.schemas import SchemaData

        return SchemaData(
            data=data,
            history=[],
            current_schema=None,
        )

    def validate(self, schema_data: SchemaData, schema: Schema) -> SchemaData:
        """Validate data against all validation rules in a schema.

        Returns a new SchemaData with the validation recorded in lineage.

        Args:
            schema_data: The SchemaData containing data and existing lineage
            schema: The Schema containing validation rules

        Returns:
            New SchemaData with validation event appended to history
        """
        import pytz

        from agent_platform.core.semantic_data_model.schemas import (
            SchemaData,
            ValidationEvent,
            ValidationResult,
        )

        results: list[ValidationResult] = []

        for rule in schema.validations:
            passed, message = self._execute_validation_rule(schema_data.data, rule)
            results.append(
                ValidationResult(
                    validation=rule,
                    passed=passed,
                    message=message,
                )
            )

        # Create validation event and append to history
        event = ValidationEvent(schema=schema, results=results, timestamp=datetime.now(pytz.utc))

        return SchemaData(
            data=schema_data.data,
            history=[*schema_data.history, event],
            current_schema=schema,
        )

    def transform(
        self,
        schema_data: SchemaData,
        transformation: Transformation,
        source_schema: Schema,
        target_schema: Schema,
    ) -> SchemaData:
        """Transform data from source schema to target schema.

        Checks if transformed data conforms to target schema shape.
        Records the transformation in lineage.

        Args:
            schema_data: The SchemaData containing data and existing lineage
            transformation: The Transformation containing the JQ expression
            source_schema: The source Schema
            target_schema: The target Schema to check conformance against

        Returns:
            New SchemaData with transformed data and updated lineage
        """
        import pytz

        from agent_platform.core.semantic_data_model.schemas import (
            SchemaData,
            TransformationEvent,
        )

        # Step 1: Execute transformation
        transformed, error = self._execute_transformation(schema_data.data, transformation)

        if error or transformed is None:
            raise ValueError(f"Transformation failed: {error}")

        # Step 2: Check if translated data conforms to target schema shape
        conforms, message = self._check_schema_conformance(transformed, target_schema)

        # Step 3: Record transformation event
        transformation_event = TransformationEvent(
            source_schema=source_schema,
            target_schema=target_schema,
            timestamp=datetime.now(pytz.UTC),
            conforms_to_target=conforms,
            message=message,
        )

        # Step 4: Return new SchemaData with transformation recorded
        return SchemaData(
            data=transformed,
            history=[*schema_data.history, transformation_event],
            current_schema=target_schema if conforms else None,
        )

    # --- Protected methods (override in subclasses for testing) ---

    def _execute_validation_rule(self, data: JsonData, rule: Validation) -> tuple[bool, str]:
        """Execute a JQ validation rule against data.

        Override this method to provide actual JQ execution.

        Args:
            data: The JSON data to validate (object or array)
            rule: The Validation rule containing the JQ expression

        Returns:
            Tuple of (passed, message) where passed is True if validation succeeded
        """
        raise NotImplementedError("JQ validation execution not yet implemented")

    def _execute_transformation(
        self, data: JsonData, transformation: Transformation
    ) -> tuple[JsonData | None, str | None]:
        """Execute a JQ expression against data.

        Override this method to provide actual JQ execution.

        Args:
            data: The JSON data to translate (object or array)
            transformation: The Transformation containing the JQ expression

        Returns:
            Tuple of (transformed_data, error) where error is None on success
        """
        raise NotImplementedError("JQ transformation execution not yet implemented")

    def _check_schema_conformance(self, data: JsonData, schema: Schema) -> tuple[bool, str]:
        """Check if data conforms to schema shape (json_schema).

        Override this method to provide actual JSON Schema validation.

        Args:
            data: The JSON data to check
            schema: The Schema containing the json_schema to validate against

        Returns:
            Tuple of (conforms, message) where conforms is True if data matches schema
        """
        raise NotImplementedError("Schema conformance check not yet implemented")


class ExtractJob:
    """Wrapper around Job that returns SchemaData from result().

    This class wraps a Reducto extraction Job and the Schema used for extraction,
    providing a result() method that automatically converts the ExtractResponse
    to SchemaData with proper lineage tracking.
    """

    def __init__(self, job: Job, schema: Schema) -> None:
        self._job = job
        self._schema = schema

    @property
    def job_id(self) -> str:
        """The underlying job ID."""
        return self._job.job_id

    async def status(self) -> JobStatus:
        """Get the current status of this job."""
        from sema4ai_docint.extraction.reducto.async_ import JobStatus

        status = await self._job.status()
        return JobStatus(status)

    async def wait(self) -> Result:
        """Wait for this job to complete and return the raw result."""
        return await self._job.wait()

    async def result(self) -> SchemaData:
        """Wait for completion and return SchemaData with lineage.

        Returns:
            SchemaData with extracted data and ExtractionEvent in history

        Raises:
            ValueError: If job failed or returned no results
        """
        from typing import Any, cast

        import pytz
        from reducto.types import ExtractResponse
        from sema4ai_docint.extraction.reducto.async_ import JobStatus

        from agent_platform.core.semantic_data_model.schemas import (
            ExtractionEvent,
            SchemaData,
        )

        # Check job status
        status = await self.status()
        if status == JobStatus.FAILED:
            raise ValueError(f"Extract job {self.job_id} failed")

        # Get the result
        raw_result = await self._job.result()
        extract_response = cast(ExtractResponse, raw_result)

        # Extract the data from the response
        if not extract_response.result:
            raise ValueError(f"Extract job {self.job_id} returned no results")

        if not isinstance(extract_response.result, dict):
            raise ValueError(f"Extract job {self.job_id} returned result that is not an object")

        # The result is a list of extracted objects; we take the first one
        # Reducto only supports returning an Object.
        extracted_data: dict[str, Any] = cast(dict[str, Any], extract_response.result[0])

        # Create extraction event for lineage
        extraction_event = ExtractionEvent(
            schema=self._schema,
            timestamp=datetime.now(pytz.UTC),
            success=True,
            message="Extraction completed successfully",
        )

        return SchemaData(
            data=extracted_data,
            history=[extraction_event],
            current_schema=self._schema,
        )


class DocumentServiceProtocol(Protocol):
    """Protocol for document extraction operations with Reducto-style ergonomics.

    Workflow:
        1. upload() - Upload file bytes, get a file_id (str)
        2. start_parse() - Start parsing, get a Job
        3. start_extract() - Start extraction from a parsed job, get a Job
        4. job.result() - Get a SchemaData with extracted data and lineage

    The Job object from sema4ai_docint has built-in methods:
        - job.status() -> JobStatus
        - job.wait() -> Result (blocks until complete)
        - job.result() -> typed response
    """

    async def upload(self, file_content: bytes) -> str:
        """Upload file bytes to the document service.

        Args:
            file_content: Raw file bytes

        Returns:
            file_id that can be passed to start_parse()
        """
        ...

    async def start_parse(self, file_id: str) -> Job:
        """Start async parsing of an uploaded document.

        Args:
            file_id: File ID from upload()

        Returns:
            Job that can be used to track status and get results
        """
        ...

    async def start_extract(
        self,
        job: Job,
        schema: Schema,
        *,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractJob:
        """Start async extraction from a parsed document using a schema.

        Args:
            job: Completed parse Job (will wait for completion if not done)
            schema: Schema with document_extraction hints
            start_page: Optional start page (1-indexed)
            end_page: Optional end page (1-indexed)

        Returns:
            Job for the extraction

        Raises:
            ValueError: If schema has no document_extraction hints
        """
        ...


class DocumentService:
    """Default implementation of DocumentServiceProtocol.

    Provides document extraction operations using Reducto via AsyncExtractionClient.
    """

    def __init__(self, *, reducto_url: str = "https://backend.sema4.ai/reducto", reducto_api_key: str) -> None:
        if not reducto_url:
            raise ValueError("reducto_url must be provided")
        if not reducto_api_key:
            raise ValueError("reducto_api_key must be provided")

        self._reducto_url = reducto_url
        self._reducto_api_key = reducto_api_key
        self._client: AsyncExtractionClient | None = None

    @property
    def client(self) -> AsyncExtractionClient:
        """Get or create the AsyncExtractionClient."""
        from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient

        if self._client is None:
            self._client = AsyncExtractionClient(
                api_key=self._reducto_api_key,
                base_url=self._reducto_url,
            )
        return self._client

    async def upload(self, file_content: bytes) -> str:
        """Upload file bytes to the document service.

        Args:
            file_content: Raw file bytes

        Returns:
            file_id that can be passed to start_parse()
        """
        return await self.client.upload(file_content)

    async def start_parse(self, file_id: str) -> Job:
        """Start async parsing of an uploaded document.

        Args:
            file_id: File ID from upload()

        Returns:
            Job that can be used to track status and get results
        """
        return await self.client.start_parse(file_id)

    async def start_extract(
        self,
        job: Job,
        schema: Schema,
        *,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> ExtractJob:
        """Start async extraction from a parsed document using a schema.

        Args:
            job: Completed parse Job (will wait for completion if not done)
            schema: Schema with document_extraction hints
            start_page: Optional start page (1-indexed)
            end_page: Optional end page (1-indexed)

        Returns:
            Job for the extraction

        Raises:
            ValueError: If schema has no document_extraction hints
        """
        if schema.document_extraction is None:
            raise ValueError(f"Schema '{schema.name}' has no document extraction hints")

        if job.job_type != JobType.PARSE:
            raise ValueError(f"start_extract() requires a Parse job, but got a {job.job_type} job")

        # Wait for parse job to complete if not already done
        await job.wait()

        extract_job = await self.client.start_extract(
            document_id=f"jobid://{job.job_id}",
            schema=schema.json_schema,
            system_prompt=schema.document_extraction.system_prompt,
            start_page=start_page,
            end_page=end_page,
            extraction_config=schema.document_extraction.configuration,
        )
        return ExtractJob(job=extract_job, schema=schema)

    async def close(self) -> None:
        """Close the underlying client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
