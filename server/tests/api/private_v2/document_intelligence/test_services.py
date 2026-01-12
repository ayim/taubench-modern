from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from reducto.types.shared import BoundingBox, ParseUsage
from reducto.types.shared.extract_response import Usage
from reducto.types.shared.parse_response import ResultFullResultChunkBlock

from agent_platform.server.api.private_v2.document_intelligence.services import (
    _create_job_result,
    _raise_mapped_reducto_error,
    _resolve_reducto_doc_id_for_extract,
)


def _make_request(**overrides):
    from agent_platform.core.document_intelligence.document_layout import (
        ResolvedExtractRequest,
    )

    base_kwargs = {
        "thread_id": "thread-123",
        "uploaded_file": None,
        "job_id": None,
        "extraction_schema": {},
        "extraction_system_prompt": None,
        "extraction_config": None,
        "data_model_prompt": None,
        "generate_citations": None,
    }
    base_kwargs.update(overrides)
    return ResolvedExtractRequest(**base_kwargs)


def _make_uploaded_file(file_id: str = "file-123"):
    from datetime import datetime

    from agent_platform.core.files.files import UploadedFile

    return UploadedFile(
        file_id=file_id,
        file_path=None,
        file_ref="file-ref",
        file_hash="file-hash",
        file_size_raw=10,
        mime_type="text/plain",
        created_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_resolve_reducto_doc_id_for_extract_prefers_job_id():
    request = _make_request(file_name="foo.pdf", job_id="job-123")
    file_manager = SimpleNamespace(read_file_contents=AsyncMock())
    extraction_client = SimpleNamespace(upload=AsyncMock())

    doc_id = await _resolve_reducto_doc_id_for_extract(
        request=request,
        user_id="user-123",
        file_manager=file_manager,  # type: ignore[arg-type]
        extraction_client=extraction_client,  # type: ignore[arg-type]
    )

    assert doc_id == "job-123"
    file_manager.read_file_contents.assert_not_awaited()
    extraction_client.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_reducto_doc_id_for_extract_uploads_file_when_present():
    uploaded_file = _make_uploaded_file()
    request = _make_request(file_name=uploaded_file.file_ref, uploaded_file=uploaded_file)

    file_contents = b"file-bytes"
    file_manager = SimpleNamespace(read_file_contents=AsyncMock(return_value=file_contents))
    extraction_client = SimpleNamespace(upload=AsyncMock(return_value="reducto-doc-123"))

    doc_id = await _resolve_reducto_doc_id_for_extract(
        request=request,
        user_id="user-123",
        file_manager=file_manager,  # type: ignore[arg-type]
        extraction_client=extraction_client,  # type: ignore[arg-type]
    )

    # Verifies that we fetched the file from agent server file storage and uploaded it to reducto
    assert doc_id == "reducto-doc-123"
    file_manager.read_file_contents.assert_awaited_once_with(uploaded_file.file_id, "user-123")
    extraction_client.upload.assert_awaited_once_with(
        file_contents,
        content_length=len(file_contents),
    )


@pytest.mark.asyncio
async def test_resolve_reducto_doc_id_for_extract_requires_reference():
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    request = _make_request(file_name="foo.pdf")  # does not have uploaded_file or job_id
    file_manager = SimpleNamespace(read_file_contents=AsyncMock())
    extraction_client = SimpleNamespace(upload=AsyncMock())

    with pytest.raises(PlatformHTTPError) as exc_info:
        await _resolve_reducto_doc_id_for_extract(
            request=request,
            user_id="user-123",
            file_manager=file_manager,  # type: ignore[arg-type]
            extraction_client=extraction_client,  # type: ignore[arg-type]
        )

    assert exc_info.value.response.error_code is ErrorCode.BAD_REQUEST


def test_create_job_result_parse_response():
    """Test that ParseResponse is properly converted to ParseJobResult."""
    from reducto.types import ParseResponse
    from reducto.types.shared.parse_response import ResultFullResult as ParseResult
    from reducto.types.shared.parse_response import ResultFullResultChunk

    from agent_platform.core.payloads.document_intelligence import ParseJobResult

    # Create a mock ParseResponse with a ParseResult containing chunks
    chunk = ResultFullResultChunk(
        blocks=[
            ResultFullResultChunkBlock(
                bbox=BoundingBox(left=0, page=0, top=0, width=0, height=0),
                content="test content",
                type="Text",
            )
        ],
        content="test content",
        embed="test embed",
    )
    parse_result = ParseResult(chunks=[chunk], type="full")
    parse_response = ParseResponse(
        result=parse_result, duration=0, job_id="test-job-123", usage=ParseUsage(num_pages=1)
    )

    job_id = "test-job-123"
    result = _create_job_result(parse_response, job_id)

    assert isinstance(result, ParseJobResult)
    assert result.job_id == "jobid://test-job-123"
    assert result.job_type == "parse"
    assert len(result.result.chunks) == 1
    assert result.result.chunks[0].content == "test content"


def test_create_job_result_extract_response_with_citations():
    """Test that ExtractResponse with citations is properly converted to ExtractJobResult."""
    from reducto.types import ExtractResponse

    from agent_platform.core.payloads.document_intelligence import ExtractJobResult

    # Create a mock ExtractResponse with both result and citations
    extract_response = ExtractResponse(
        usage=Usage(num_pages=1, num_fields=1),
        result=[{"field1": "value1", "field2": "value2"}],
        citations=[{"fake_citations": True}],
    )

    job_id = "extract-job-789"
    result = _create_job_result(extract_response, job_id)

    assert isinstance(result, ExtractJobResult)
    assert result.job_id == "jobid://extract-job-789"
    assert result.job_type == "extract"
    assert result.result == {"field1": "value1", "field2": "value2"}
    assert result.citations == {"fake_citations": True}


def test_create_job_result_split_response():
    """Test that SplitResponse is properly converted to SplitJobResult."""
    from reducto.types import SplitResponse
    from reducto.types.shared.split_response import Result as SplitResult
    from reducto.types.shared.split_response import ResultSplit

    from agent_platform.core.payloads.document_intelligence import SplitJobResult

    # Create a mock SplitResponse with a SplitResult
    split_response = SplitResponse(
        result=SplitResult(
            section_mapping={"balance sheets": [1, 2]},
            splits=[ResultSplit(name="balance sheets", pages=[1, 2], conf="high")],
        ),
        usage=ParseUsage(num_pages=1),
    )

    job_id = "split-job-999"
    actual = _create_job_result(split_response, job_id)

    assert isinstance(actual, SplitJobResult)
    assert actual.job_id == "jobid://split-job-999"
    assert actual.job_type == "split"
    assert actual.result.section_mapping == split_response.result.section_mapping
    assert actual.result.splits == split_response.result.splits


def test_create_job_result_unexpected_type():
    """Test that an unexpected result type raises PlatformHTTPError."""
    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    # Pass an unexpected type (e.g., a string)
    unexpected_result = "not a valid response type"
    job_id = "bad-job-000"

    with pytest.raises(PlatformHTTPError) as exc_info:
        _create_job_result(unexpected_result, job_id)

    assert exc_info.value.response.error_code is ErrorCode.UNEXPECTED
    assert "Unexpected result type" in exc_info.value.response.message


def test_raise_mapped_reducto_error_job_failed_schema_validation():
    """Test that JobFailedError with schema validation errors maps to UNPROCESSABLE_ENTITY."""
    from sema4ai_docint.extraction.reducto.exceptions import JobFailedError

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    # Test schema validation errors (should be 422)
    schema_error_messages = [
        "Conflicting keys after snake_case normalization: 'Billed To' conflicts with 'billed_to'",
        "Invalid schema provided",
        "Schema validation failed: duplicate key found",
    ]

    for error_msg in schema_error_messages:
        error = JobFailedError(reason=error_msg, job_id="test-job-123")
        with pytest.raises(PlatformHTTPError) as exc_info:
            _raise_mapped_reducto_error(error)

        assert exc_info.value.response.error_code is ErrorCode.UNPROCESSABLE_ENTITY
        assert exc_info.value.response.status_code == 422
        assert "schema" in exc_info.value.response.message.lower()


def test_raise_mapped_reducto_error_job_failed_other_reasons():
    """Test that JobFailedError with non-schema errors maps to UNPROCESSABLE_ENTITY."""
    from sema4ai_docint.extraction.reducto.exceptions import JobFailedError

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    # Test other job failures (should be 422 - document processing issue, not server error)
    error = JobFailedError(reason="Unknown processing error", job_id="test-job-456")
    with pytest.raises(PlatformHTTPError) as exc_info:
        _raise_mapped_reducto_error(error)

    assert exc_info.value.response.error_code is ErrorCode.UNPROCESSABLE_ENTITY
    assert exc_info.value.response.status_code == 422


def test_raise_mapped_reducto_error_extract_failed():
    """Test that ExtractFailedError maps to UNPROCESSABLE_ENTITY."""
    from sema4ai_docint.extraction.reducto.exceptions import ExtractFailedError

    from agent_platform.core.errors.base import PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    error = ExtractFailedError("Extraction failed")
    with pytest.raises(PlatformHTTPError) as exc_info:
        _raise_mapped_reducto_error(error)

    assert exc_info.value.response.error_code is ErrorCode.UNPROCESSABLE_ENTITY
    assert exc_info.value.response.status_code == 422
