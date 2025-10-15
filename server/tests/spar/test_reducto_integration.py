from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import TypedDict

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from reducto.types.shared.parse_response import ResultFullResultChunk
from sema4ai_docint.extraction.reducto.async_ import JobType

from agent_platform.core.payloads.document_intelligence import (
    DocumentLayoutPayload,
    ExtractDocumentPayload,
)
from agent_platform.core.payloads.upsert_document_layout import _ExtractionSchema

from .helpers import upload_file_to_thread


class ExtractionSchemaResult(TypedDict):
    file: None
    schema: dict
    resource_name: str


@pytest.mark.spar
class TestReductoIntegration:
    def _assert_tables_pdf_parse_result(self, parse_result_json: dict) -> None:
        """Helper function to assert the parse result for tables.pdf matches expected structure."""
        # The API now returns {"chunks": [...]}, validate chunks directly
        assert "chunks" in parse_result_json, "Expected 'chunks' key in parse result"
        chunks_data = parse_result_json["chunks"]
        assert len(chunks_data) > 0, "Expected at least one chunk in parse result"

        # Validate the first chunk structure
        first_chunk = ResultFullResultChunk.model_validate(chunks_data[0])
        blocks = first_chunk.blocks

        # Should have multiple blocks (around 17-20 based on the sample)
        assert len(blocks) >= 15, f"Expected at least 15 blocks, got {len(blocks)}"

        # Check for required fields in each block
        for block in blocks:
            assert block.confidence == "high"

        # Check for specific content markers to ensure we parsed the right document
        content = first_chunk.content

        # Should contain table structures
        assert "<table>" in content
        assert "</table>" in content

        # Should contain the expected headers/sections
        expected_sections = [
            "Simple Table",
            "Simple Table with gaps",
            "Simple Table with gaps in first row/col",
            "Non Simple Table",
            "Non Simple Table with Merged Columns",
            "Non Simple Table with Merged Rows and Columns",
            "Over the page",
        ]

        for section in expected_sections:
            assert section in content, f"Expected section '{section}' not found in content"

        # Check for table headers that should be present
        table_headers = ["Heading 1", "Heading 2", "Heading 3", "Heading 4"]
        for header in table_headers:
            assert header in content, f"Expected table header '{header}' not found"

        # Check for table data elements
        table_data_elements = [
            "<td>A</td>",
            "<td>B</td>",
            "<td>C</td>",
            "<td>1</td>",
            "<td>2</td>",
            "<td>3</td>",
        ]
        for element in table_data_elements:
            assert element in content, f"Expected table data '{element}' not found"

        # Check that embed content matches content (as per sample)
        assert first_chunk.embed == first_chunk.content

        # Verify we have blocks spanning across pages (page 1 and 2)
        pages = {block.bbox.page for block in blocks}
        assert 1 in pages, "Expected blocks from page 1"
        assert 2 in pages, "Expected blocks from page 2"

    def _upload_resource_to_new_agent_thread(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
        resource_name: str,
    ) -> tuple[str, str, str]:
        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)
        resource_path = spar_resources_path / resource_name
        file_upload_result = upload_file_to_thread(
            agent_server_client_with_doc_int, thread_id, resource_path
        )
        return thread_id, file_upload_result.file_ref, agent_id

    @pytest.mark.parametrize("resource_name", ["tables.pdf"])
    def test_document_parse(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
        resource_name: str,
    ):
        thread_id, file_ref, _ = self._upload_resource_to_new_agent_thread(
            agent_server_client_with_doc_int, agent_factory, spar_resources_path, resource_name
        )

        # perform the parse
        parse_result = agent_server_client_with_doc_int.parse_document(file_ref, thread_id)

        # assert the parse result matches expected structure
        self._assert_tables_pdf_parse_result(parse_result)

    @pytest.mark.parametrize("resource_name", ["tables.pdf"])
    def test_async_document_parse(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
        resource_name: str,
    ):
        thread_id, file_ref, _ = self._upload_resource_to_new_agent_thread(
            agent_server_client_with_doc_int, agent_factory, spar_resources_path, resource_name
        )

        # Get a job
        job_result = agent_server_client_with_doc_int.start_async_document_parse(
            file_ref, thread_id
        )

        # Assert the job result matches expected structure
        assert "job_id" in job_result
        job_id = job_result["job_id"]
        assert isinstance(job_id, str)
        assert "job_type" in job_result
        assert job_result["job_type"] == JobType.PARSE.value

        # check status
        status_result = agent_server_client_with_doc_int.get_job_status(job_id, JobType.PARSE)
        assert "status" in status_result
        # To avoid race condition, we will access "Completed" on first poll
        assert status_result["status"] in ["Pending", "Completed"]

        result_url = status_result["result_url"]
        while result_url is None:
            sleep(1)
            status_result = agent_server_client_with_doc_int.get_job_status(job_id, JobType.PARSE)
            result_url = status_result["result_url"]

        # check result url is the expected one
        assert job_id in result_url, f"result_url {result_url!r} does not contain job_id {job_id!r}"

        # get the result
        result_result = agent_server_client_with_doc_int.get_job_result(job_id, JobType.PARSE)
        assert "result" in result_result
        assert "job_type" in result_result
        assert result_result["job_type"] == JobType.PARSE.value
        self._assert_tables_pdf_parse_result(result_result["result"])

    @pytest.fixture
    def extraction_schema_result(
        self,
        request: pytest.FixtureRequest,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
    ) -> ExtractionSchemaResult:
        """Fixture that generates extraction schema from the parametrized document."""
        resource_name: str = request.param
        thread_id, file_ref, agent_id = self._upload_resource_to_new_agent_thread(
            agent_server_client_with_doc_int, agent_factory, spar_resources_path, resource_name
        )

        # generate the extraction schema
        extraction_schema = agent_server_client_with_doc_int.generate_extraction_schema(
            file_ref, thread_id, agent_id
        )
        return {
            "file": extraction_schema["file"],
            "schema": extraction_schema["schema"],
            "resource_name": resource_name,
        }

    @pytest.mark.parametrize("extraction_schema_result", ["tables.pdf"], indirect=True)
    def test_generate_extraction_schema_from_document(
        self,
        extraction_schema_result: ExtractionSchemaResult,
    ):
        """Test that the generated extraction schema has the expected structure."""

        schema = extraction_schema_result["schema"]

        # Minimal checking as the actual shape of the schema can vary a lot
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema["properties"] is not None
        assert "required" in schema
        assert schema["required"] is not None

    @pytest.mark.parametrize("extraction_schema_result", ["tables.pdf"], indirect=True)
    @pytest.mark.parametrize("generate_citations", [True, False])
    def test_extract_document_with_transient_schema(
        self,
        extraction_schema_result: ExtractionSchemaResult,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
        generate_citations: bool,
    ):
        """Test that the document can be extracted with a transient schema."""
        resource_name = extraction_schema_result["resource_name"]

        thread_id, _, _ = self._upload_resource_to_new_agent_thread(
            agent_server_client_with_doc_int, agent_factory, spar_resources_path, resource_name
        )

        # Create a document layout with the extraction schema
        document_layout = DocumentLayoutPayload(
            extraction_schema=_ExtractionSchema.model_validate(extraction_schema_result["schema"]),
        )
        extract_request = ExtractDocumentPayload(
            file_name=resource_name,
            thread_id=thread_id,
            document_layout=document_layout,
            generate_citations=generate_citations,
        )

        extract_results = agent_server_client_with_doc_int.extract_document(extract_request)

        # Validate that we got results
        assert extract_results is not None
        assert isinstance(extract_results, dict)
        assert "result" in extract_results
        assert len(extract_results["result"]) > 0

        # Check citations based on generate_citations parameter
        assert "citations" in extract_results
        if generate_citations:
            assert extract_results["citations"] is not None
            assert len(extract_results["citations"]) > 0
        else:
            assert extract_results["citations"] is None
