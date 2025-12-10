"""Integration tests for document tools (parse_document and generate_schema).

These tests verify that the document intelligence functionality works correctly
when called via kernel tools during agent execution.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient

from .helpers import upload_file_to_thread


@pytest.mark.spar
class TestDocumentToolsIntegration:
    """Test document parse and schema generation via API (which kernel tools use internally)."""

    def test_parse_document_via_api(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
    ):
        """Test that parse_document API works (used by parse_document tool)."""
        # Create agent and thread
        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        # Upload a PDF file
        resource_path = spar_resources_path / "tables.pdf"
        file_result = upload_file_to_thread(
            agent_server_client_with_doc_int, thread_id, resource_path
        )

        # Call parse_document (same API the tool uses)
        parse_result = agent_server_client_with_doc_int.parse_document(
            file_ref=file_result.file_ref,
            agent_id=agent_id,
            thread_id=thread_id,
        )

        # Verify we got chunks back
        assert parse_result.result is not None
        assert parse_result.result.chunks is not None
        assert len(parse_result.result.chunks) > 0, "Should have parsed chunks"

        # Verify content contains table data
        first_chunk = parse_result.result.chunks[0]
        content = first_chunk.content
        assert "<table>" in content, "Should contain table markup"
        assert "Heading" in content, "Should contain table headers"

    def test_generate_schema_via_api(
        self,
        agent_server_client_with_doc_int: AgentServerClient,
        agent_factory: Callable[[], str],
        spar_resources_path: Path,
    ):
        """Test that generate_schema API works (used by generate_schema tool)."""
        # Create agent and thread
        agent_id = agent_factory()
        thread_id = agent_server_client_with_doc_int.create_thread_and_return_thread_id(agent_id)

        # Upload an invoice PDF
        resource_path = spar_resources_path / "sample_invoice_1.pdf"
        file_result = upload_file_to_thread(
            agent_server_client_with_doc_int, thread_id, resource_path
        )

        # Call generate_extraction_schema (same API the tool uses)
        schema_result = agent_server_client_with_doc_int.generate_extraction_schema(
            file_ref=file_result.file_ref,
            thread_id=thread_id,
            agent_id=agent_id,
        )

        # Verify we got a valid JSON schema back
        assert schema_result.schema is not None, "Should return a schema"
        assert "type" in schema_result.schema, "Schema should have a type field"
        assert schema_result.schema["type"] == "object", "Schema should be object type"
        assert "properties" in schema_result.schema, "Schema should have properties"
