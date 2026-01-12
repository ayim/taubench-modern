"""Tests for DocumentServiceV2 (_DocumentServiceV2)."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from reducto.types.shared import BoundingBox, ParseResponse, ParseUsage
from reducto.types.shared.parse_response import (
    ResultFullResult,
    ResultFullResultChunk,
    ResultFullResultChunkBlock,
)

from sema4ai_docint.extraction.reducto import AsyncExtractionClient
from sema4ai_docint.models.document_v2 import DocumentV2
from sema4ai_docint.services._context import _DIContext
from sema4ai_docint.services._document_v2 import _DocumentServiceV2
from sema4ai_docint.services.persistence.directory import DirectoryPersistenceService


class TestDocumentServiceV2:
    """Test suite for DocumentServiceV2 focusing on caching and force_reload functionality."""

    @pytest.fixture
    def test_pdf_path(self, tmp_path) -> Path:
        """Return path to test PDF file."""
        p = tmp_path / "INV-00001.pdf"
        if not p.exists():
            import shutil

            shutil.copy(Path(__file__).parent / "assets" / "INV-00001.pdf", p)
        return p

    @pytest.fixture
    def mock_extraction_service_async(self) -> AsyncExtractionClient:
        """Create a mock extraction service that returns static parse responses."""
        service = AsyncExtractionClient(api_key="fake-api-key")

        async def _mock_parse(*args, **kwargs) -> ParseResponse:
            """Mock parse method that returns static ParseResponse."""
            # Create mock chunks that match ResultFullResultChunk structure
            chunk = ResultFullResultChunk(
                blocks=[
                    ResultFullResultChunkBlock.model_construct(
                        bbox=BoundingBox.model_construct(
                            height=50.0,
                            left=50.0,
                            page=1,
                            top=700.0,
                            width=250.0,
                            original_page=1,
                        ),
                        content=(
                            "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                            "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                            "Dallas, TX 75201"
                        ),
                        type="Text",
                        confidence="high",
                        image_url=None,
                    )
                ],
                content=(
                    "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                    "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                    "Dallas, TX 75201"
                ),
                embed=(
                    "INVOICE\nInvoice Number: INV-00001\nDate: August 20, 2025\n"
                    "Bill To: Avenue University\n123 University Ave\nSuite 456\n"
                    "Dallas, TX 75201"
                ),
            )

            return ParseResponse.model_construct(
                result=ResultFullResult(
                    chunks=[chunk],
                    type="full",
                ),
                duration=2.5,
                job_id="test-job-123",
                usage=ParseUsage.model_construct(
                    num_pages=1,
                    credits=10.0,
                ),
            )

        # Use Mock with side_effect to track calls
        service.parse = AsyncMock(side_effect=_mock_parse)  # type: ignore
        service.upload = AsyncMock(return_value="test-reducto-file-id")  # type: ignore
        return service

    @pytest.fixture
    def persistence_service(self, tmp_path: Path) -> DirectoryPersistenceService:
        """Create a persistence service using a temporary directory for caching."""
        return DirectoryPersistenceService(tmp_path)

    @pytest.fixture
    def mock_transport(self, test_pdf_path):
        """Create a mock transport that returns the test PDF."""
        from tests.agent_server_client.conftest import MockTransport

        transport = MockTransport(agent_id="test_agent")
        transport.set_file_responses({"INV-00001.pdf": test_pdf_path})
        return transport

    @pytest.fixture
    def context_v2(
        self,
        postgres_datasource,
        mock_extraction_service_async,
        mock_transport,
        persistence_service,
    ) -> _DIContext:
        """Create a context for DocumentServiceV2 with mocked dependencies."""
        return _DIContext(
            datasource=postgres_datasource,
            extraction_service_async=mock_extraction_service_async,
            agent_server_transport=mock_transport,
            persistence_service=persistence_service,
        )

    @pytest.fixture
    def document_service_v2(self, context_v2) -> _DocumentServiceV2:
        """Create a DocumentServiceV2 instance for testing."""
        return _DocumentServiceV2(context_v2)

    @pytest_asyncio.fixture
    async def sample_document(self, document_service_v2, test_pdf_path: Path) -> DocumentV2:
        """Create a sample document for testing."""
        return await document_service_v2.new_document(test_pdf_path.name)

    @pytest.mark.asyncio
    async def test_new_document_from_string(
        self, document_service_v2, mock_transport, test_pdf_path: Path
    ):
        """Test creating a new document from a string (file reference)."""
        mock_transport.set_file_responses({test_pdf_path.name: test_pdf_path})

        document = await document_service_v2.new_document(test_pdf_path.name)

        assert isinstance(document, DocumentV2)
        assert document.file_name == "INV-00001.pdf"
        assert document.document_id is not None

    @pytest.mark.asyncio
    async def test_parse_first_call_uses_extraction_service(
        self, document_service_v2, sample_document: DocumentV2, mock_extraction_service_async
    ):
        """Test that the first parse call uses the extraction service."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # First call should use extraction service
        result = await document_service_v2.parse(sample_document)

        # Verify extraction service was called exactly once
        assert mock_extraction_service_async.parse.call_count == 1

        # Verify result is a valid ParseResponse
        assert isinstance(result, ParseResponse)
        assert result.job_id == "test-job-123"
        assert result.duration == 2.5

    @pytest.mark.asyncio
    async def test_parse_second_call_uses_cache(
        self, document_service_v2, sample_document: DocumentV2, mock_extraction_service_async
    ):
        """Test that subsequent parse calls use the cache and don't call extraction service."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # First call - should use extraction service
        result1 = await document_service_v2.parse(sample_document)
        assert mock_extraction_service_async.parse.call_count == 1

        # Second call - should use cache (no additional calls to extraction service)
        result2 = await document_service_v2.parse(sample_document)
        assert mock_extraction_service_async.parse.call_count == 1  # Still 1, not 2

        # Results should be equivalent
        assert result1.job_id == result2.job_id
        assert result1.duration == result2.duration
        assert len(result1.result.chunks) == len(result2.result.chunks)

    @pytest.mark.asyncio
    async def test_parse_multiple_calls_cache_effectiveness(
        self, document_service_v2, sample_document, mock_extraction_service_async
    ):
        """Test that cache is effective across multiple calls."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # Make multiple parse calls
        results = []
        for _ in range(5):
            result = await document_service_v2.parse(sample_document)
            results.append(result)

        # Extraction service should only be called once
        assert mock_extraction_service_async.parse.call_count == 1

        # All results should be equivalent
        for result in results:
            assert result.job_id == "test-job-123"
            assert result.duration == 2.5

    @pytest.mark.asyncio
    async def test_parse_force_reload_bypasses_cache(
        self, document_service_v2, sample_document, mock_extraction_service_async
    ):
        """Test that force_reload=True bypasses cache and calls extraction service."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # First call - populates cache
        result1 = await document_service_v2.parse(sample_document)
        assert mock_extraction_service_async.parse.call_count == 1

        # Second call with force_reload=False - uses cache
        result2 = await document_service_v2.parse(sample_document, force_reload=False)
        assert mock_extraction_service_async.parse.call_count == 1  # Still 1

        # Third call with force_reload=True - bypasses cache
        result3 = await document_service_v2.parse(sample_document, force_reload=True)
        assert mock_extraction_service_async.parse.call_count == 2  # Now 2

        # All results should be equivalent (same mock data)
        assert result1.job_id == result2.job_id == result3.job_id

    @pytest.mark.asyncio
    async def test_parse_force_reload_updates_cache(
        self, document_service_v2, sample_document, mock_extraction_service_async
    ):
        """Test that force_reload=True updates the cache with fresh data."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # First call - populates cache
        await document_service_v2.parse(sample_document)
        assert mock_extraction_service_async.parse.call_count == 1

        # Force reload - should call extraction service and update cache
        await document_service_v2.parse(sample_document, force_reload=True)
        assert mock_extraction_service_async.parse.call_count == 2

        # Subsequent call without force_reload should use updated cache
        await document_service_v2.parse(sample_document, force_reload=False)
        assert mock_extraction_service_async.parse.call_count == 2  # Still 2, not 3

    @pytest.mark.asyncio
    async def test_parse_caches_per_document_id(
        self, document_service_v2, test_pdf_path: Path, mock_extraction_service_async
    ):
        """Test that caching is per-document (different documents get different cache entries)."""
        # Reset call count
        mock_extraction_service_async.parse.reset_mock()

        # Create and parse first document
        doc1 = await document_service_v2.new_document(test_pdf_path.name)
        await document_service_v2.parse(doc1)
        assert mock_extraction_service_async.parse.call_count == 1

        # Parse same document again - should use cache
        await document_service_v2.parse(doc1)
        assert mock_extraction_service_async.parse.call_count == 1

        # Create a "different" document (in reality, same file, so same document_id)
        # This tests that the same file gets the same cache entry
        doc2 = await document_service_v2.new_document(test_pdf_path.name)
        assert doc1.document_id == doc2.document_id

        # Parse doc2 - should use same cache as doc1
        await document_service_v2.parse(doc2)
        assert mock_extraction_service_async.parse.call_count == 1

    @pytest.mark.asyncio
    async def test_parse_cached_data_structure(
        self, document_service_v2, sample_document: DocumentV2, persistence_service
    ):
        """Test that cached data can be deserialized back to ParseResponse."""
        from sema4ai_docint.services.persistence import DocumentOperationType

        # Parse document to populate cache
        original_result = await document_service_v2.parse(sample_document)

        # Load from cache directly using the correct cache key
        cache_key = persistence_service.cache_key_for(
            sample_document.file_name, DocumentOperationType.PARSE
        )
        cached_bytes = await persistence_service.load(cache_key)
        assert cached_bytes is not None

        # Deserialize cached data
        cached_result = ParseResponse.model_validate_json(cached_bytes)

        # Verify structure matches
        assert cached_result.job_id == original_result.job_id
        assert cached_result.duration == original_result.duration
        assert len(cached_result.result.chunks) == len(original_result.result.chunks)

    @pytest.mark.asyncio
    async def test_get_schema_returns_without_metadata(
        self, document_service_v2, sample_document: DocumentV2, context_v2
    ):
        """Test that get_schema returns schema WITHOUT user_prompt metadata."""
        from unittest.mock import Mock

        user_prompt = "Extract all invoice details."
        expected_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
            },
        }

        # Mock the agent_client.generate_schema
        context_v2.agent_client.generate_schema = Mock(return_value=expected_schema)

        # First generate a schema with user_prompt to populate cache
        await document_service_v2.generate_schema(
            sample_document,
            user_prompt=user_prompt,
        )

        # Now get the cached schema using get_schema
        cached_schema = await document_service_v2.get_schema(sample_document)

        # Verify schema is returned WITHOUT user_prompt
        assert cached_schema is not None
        assert cached_schema == expected_schema
        assert "user_prompt" not in cached_schema

    @pytest.mark.asyncio
    async def test_get_schema_with_metadata_returns_with_metadata(
        self, document_service_v2, sample_document: DocumentV2, context_v2
    ):
        """Test that get_schema_with_metadata returns schema WITH user_prompt metadata."""
        from unittest.mock import Mock

        user_prompt = "Extract all invoice details."
        expected_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
            },
        }

        # Mock the agent_client.generate_schema
        context_v2.agent_client.generate_schema = Mock(return_value=expected_schema)

        # First generate a schema with user_prompt to populate cache
        await document_service_v2.generate_schema(
            sample_document,
            user_prompt=user_prompt,
        )

        # Now get the cached schema WITH metadata
        cached_schema_with_metadata = await document_service_v2.get_schema_with_metadata(
            sample_document
        )

        # Verify schema is returned WITH user_prompt
        assert cached_schema_with_metadata is not None
        assert cached_schema_with_metadata.user_prompt == user_prompt
        assert cached_schema_with_metadata.extract_schema["type"] == "object"
        assert (
            cached_schema_with_metadata.extract_schema["properties"]
            == expected_schema["properties"]
        )

    @pytest.mark.asyncio
    async def test_get_schema_returns_none_when_no_cache(
        self, document_service_v2, sample_document: DocumentV2
    ):
        """Test that get_schema returns None when no cached schema exists."""
        # Don't generate any schema, cache should be empty
        cached_schema = await document_service_v2.get_schema(sample_document)

        assert cached_schema is None

    @pytest.mark.asyncio
    async def test_get_schema_with_metadata_returns_none_when_no_cache(
        self, document_service_v2, sample_document: DocumentV2
    ):
        """Test that get_schema_with_metadata returns None when no cached schema exists."""
        # Don't generate any schema, cache should be empty
        cached_schema = await document_service_v2.get_schema_with_metadata(sample_document)

        assert cached_schema is None

    @pytest.mark.asyncio
    async def test_generate_schema_force_reload_updates_user_prompt(
        self, document_service_v2, sample_document: DocumentV2, context_v2
    ):
        """Test that force_reload=True updates the cached user_prompt."""
        from unittest.mock import Mock

        schema_v1 = {
            "type": "object",
            "properties": {"invoice_number": {"type": "string"}},
        }
        schema_v2 = {
            "type": "object",
            "properties": {"invoice_number": {"type": "string"}, "total": {"type": "number"}},
        }

        # Mock to return different schemas on subsequent calls
        context_v2.agent_client.generate_schema = Mock(side_effect=[schema_v1, schema_v2])

        # Generate schema with first user_prompt
        user_prompt_v1 = "Extract invoice number only."
        await document_service_v2.generate_schema(
            sample_document,
            user_prompt=user_prompt_v1,
        )

        # Verify first user_prompt is cached
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached.user_prompt == user_prompt_v1

        # Force reload with different user_prompt
        user_prompt_v2 = "Extract invoice number and total."
        await document_service_v2.generate_schema(
            sample_document,
            force_reload=True,
            user_prompt=user_prompt_v2,
        )

        # Verify the cached user_prompt was updated
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached.user_prompt == user_prompt_v2

    @pytest.mark.asyncio
    async def test_generate_schema_uses_parse_response(
        self,
        document_service_v2,
        sample_document: DocumentV2,
        context_v2,
        mock_extraction_service_async,
    ):
        """Test that generate_schema uses Reducto parse response for all file formats."""
        from unittest.mock import Mock

        expected_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "date": {"type": "string"},
            },
        }

        # Mock the agent_client.generate_schema to capture the parse_response parameter
        context_v2.agent_client.generate_schema = Mock(return_value=expected_schema)

        # Generate schema
        schema = await document_service_v2.generate_schema(sample_document)

        # Verify schema was generated
        assert schema == expected_schema

        # Verify parse was called (for Reducto parsing)
        assert mock_extraction_service_async.parse.call_count == 1

        # Verify agent_client.generate_schema was called with parse_response
        assert context_v2.agent_client.generate_schema.call_count == 1
        call_kwargs = context_v2.agent_client.generate_schema.call_args.kwargs
        assert "parse_response" in call_kwargs
        assert call_kwargs["parse_response"] is not None

        # Verify the parse_response is a ParseResponse object
        parse_response = call_kwargs["parse_response"]
        assert hasattr(parse_response, "result")
        assert hasattr(parse_response, "job_id")

    @pytest.mark.asyncio
    async def test_generate_schema_with_page_range_applies_to_parse(
        self,
        document_service_v2,
        sample_document: DocumentV2,
        context_v2,
        mock_extraction_service_async,
    ):
        """Test that start_page/end_page parameters are applied to Reducto parse config."""
        from unittest.mock import Mock

        expected_schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        }

        context_v2.agent_client.generate_schema = Mock(return_value=expected_schema)

        # Generate schema with page range
        await document_service_v2.generate_schema(
            sample_document,
            start_page=2,
            end_page=5,
        )

        # Verify parse was called with page range config
        assert mock_extraction_service_async.parse.call_count == 1
        parse_call_kwargs = mock_extraction_service_async.parse.call_args.kwargs
        assert "config" in parse_call_kwargs
        config = parse_call_kwargs["config"]
        assert config is not None
        assert "advanced_options" in config
        assert "page_range" in config["advanced_options"]
        assert config["advanced_options"]["page_range"]["start"] == 2
        assert config["advanced_options"]["page_range"]["end"] == 5

    @pytest.mark.asyncio
    async def test_generate_schema_leverages_parse_cache(
        self,
        document_service_v2,
        sample_document: DocumentV2,
        context_v2,
        mock_extraction_service_async,
    ):
        """Test that generate_schema reuses cached parse response."""
        from unittest.mock import Mock

        expected_schema = {
            "type": "object",
            "properties": {"invoice_number": {"type": "string"}},
        }

        context_v2.agent_client.generate_schema = Mock(return_value=expected_schema)

        # First call: parse the document
        await document_service_v2.parse(sample_document)
        assert mock_extraction_service_async.parse.call_count == 1

        # Second call: generate schema (should reuse parse cache)
        await document_service_v2.generate_schema(sample_document)

        # Verify parse was NOT called again (cache was used)
        assert mock_extraction_service_async.parse.call_count == 1

        # But generate_schema was called
        assert context_v2.agent_client.generate_schema.call_count == 1

    @pytest.mark.asyncio
    async def test_extract_document_caches_schema(
        self,
        mock_extraction_service_async,
        mock_transport,
        persistence_service,
        test_pdf_path: Path,
    ):
        """Test that extract_document saves the extraction schema to SCHEMA cache."""
        from sema4ai_docint.models import ExtractionResult

        # Create a minimal context without postgres_datasource since we don't need it
        context = _DIContext(
            datasource=None,
            extraction_service_async=mock_extraction_service_async,
            agent_server_transport=mock_transport,
            persistence_service=persistence_service,
        )
        document_service_v2 = _DocumentServiceV2(context)

        # Create sample document
        sample_document = await document_service_v2.new_document(test_pdf_path.name)

        extraction_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "date": {"type": "string"},
                "total": {"type": "number"},
            },
        }

        prompt = "Extract invoice details from the document."

        # Mock extract_with_schema to return a result
        mock_extraction_service_async.extract_with_schema = AsyncMock(
            return_value=ExtractionResult(
                results={
                    "invoice_number": "INV-00001",
                    "date": "August 20, 2025",
                    "total": 150.00,
                },
                citations={},
            )
        )

        # Extract document with schema
        result = await document_service_v2.extract_document(
            sample_document,
            extraction_schema=extraction_schema,
            prompt=prompt,
        )

        # Verify extraction was successful
        assert result.results["invoice_number"] == "INV-00001"
        assert result.results["total"] == 150.00

        cached_schema_with_metadata = await document_service_v2.get_schema_with_metadata(
            sample_document
        )
        assert cached_schema_with_metadata is not None
        assert cached_schema_with_metadata.extract_schema == extraction_schema
        # extract_document saves schema with user_prompt=None
        assert cached_schema_with_metadata.user_prompt is None

    @pytest.mark.asyncio
    async def test_extract_document_preserves_existing_user_prompt(
        self,
        mock_extraction_service_async,
        mock_transport,
        persistence_service,
        test_pdf_path: Path,
    ):
        """Test that extract_document doesn't overwrite existing schema."""
        from unittest.mock import Mock

        from sema4ai_docint.models import ExtractionResult

        # Create context with agent_client mock
        context = _DIContext(
            datasource=None,
            extraction_service_async=mock_extraction_service_async,
            agent_server_transport=mock_transport,
            persistence_service=persistence_service,
        )
        document_service_v2 = _DocumentServiceV2(context)

        # Create sample document
        sample_document = await document_service_v2.new_document(test_pdf_path.name)

        extraction_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "date": {"type": "string"},
                "total": {"type": "number"},
            },
        }

        # First, generate a schema with a user_prompt
        user_prompt = "Extract all invoice details with special attention to dates."
        context.agent_client.generate_schema = Mock(return_value=extraction_schema)
        await document_service_v2.generate_schema(
            sample_document,
            user_prompt=user_prompt,
        )

        # Verify the schema was cached with the user_prompt
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached is not None
        assert cached.user_prompt == user_prompt
        assert cached.extract_schema == extraction_schema

        # Now extract with the same schema (but different prompt parameter)
        mock_extraction_service_async.extract_with_schema = AsyncMock(
            return_value=ExtractionResult(
                results={
                    "invoice_number": "INV-00001",
                    "date": "August 20, 2025",
                    "total": 150.00,
                },
                citations={},
            )
        )

        await document_service_v2.extract_document(
            sample_document,
            extraction_schema=extraction_schema,
            prompt="Different prompt for extraction",
        )

        # Verify the cached schema still has the original user_prompt
        # (it wasn't overwritten by extract_document)
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached is not None
        assert cached.user_prompt == user_prompt  # Should still be the original
        assert cached.extract_schema == extraction_schema

    @pytest.mark.asyncio
    async def test_extract_document_updates_schema_if_different(
        self,
        mock_extraction_service_async,
        mock_transport,
        persistence_service,
        test_pdf_path: Path,
    ):
        """Test that extract_document updates schema cache if different."""
        from unittest.mock import Mock

        from sema4ai_docint.models import ExtractionResult

        # Create context with agent_client mock
        context = _DIContext(
            datasource=None,
            extraction_service_async=mock_extraction_service_async,
            agent_server_transport=mock_transport,
            persistence_service=persistence_service,
        )
        document_service_v2 = _DocumentServiceV2(context)

        # Create sample document
        sample_document = await document_service_v2.new_document(test_pdf_path.name)

        # First schema
        first_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
            },
        }

        # Generate first schema with user_prompt
        user_prompt = "Extract invoice number only."
        context.agent_client.generate_schema = Mock(return_value=first_schema)
        await document_service_v2.generate_schema(
            sample_document,
            user_prompt=user_prompt,
        )

        # Verify first schema was cached
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached is not None
        assert cached.user_prompt == user_prompt
        assert cached.extract_schema == first_schema

        # Extract with a DIFFERENT schema
        second_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "date": {"type": "string"},
                "total": {"type": "number"},
            },
        }

        mock_extraction_service_async.extract_with_schema = AsyncMock(
            return_value=ExtractionResult(
                results={
                    "invoice_number": "INV-00001",
                    "date": "August 20, 2025",
                    "total": 150.00,
                },
                citations={},
            )
        )

        await document_service_v2.extract_document(
            sample_document,
            extraction_schema=second_schema,
            prompt="Extract all fields",
        )

        # Verify the cached schema was updated to the new schema
        cached = await document_service_v2.get_schema_with_metadata(sample_document)
        assert cached is not None
        assert cached.extract_schema == second_schema
        # Since schema was different, it should be saved with user_prompt=None
        assert cached.user_prompt is None
