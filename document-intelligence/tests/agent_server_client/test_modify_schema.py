"""Tests for the modify_schema method in AgentServerClient."""

import json
from collections.abc import Callable

import pytest

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.agent_server_client.transport.base import ResponseMessage
from tests.agent_server_client.conftest import MockTransport


@pytest.mark.schema_eval
class TestEvalModifySchema:
    """Test suite for schema modification functionality."""

    @pytest.fixture(autouse=True)
    def check_eval_marker(self, request):
        """Check if schema_eval marker is being used, skip if not."""
        if "schema_eval" not in request.config.getoption("-m", default=""):
            pytest.skip("This test requires the schema_eval marker to run")

    def test_modify_schema_basic(self, agent_client: AgentServerClient):
        """Test basic schema modification without file context."""

        # Create a sample schema to modify
        original_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's full name"},
                "age": {"type": "integer", "description": "Person's age in years"},
            },
            "required": ["name"],
        }

        # Modification instructions
        instructions = (
            "Add an email field that is required and must match email format. "
            "Also make age field required."
        )

        # Modify the schema
        result = agent_client.modify_schema(
            schema=original_schema, modification_instructions=instructions
        )

        # Verify the result
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("type") == "object"

        # TODO: These assertions are flaky because they check non-deterministic behavior
        # Check that email was added
        properties = result.get("properties", {})
        assert "email" in properties
        assert properties["email"]["type"] == "string"

        # Check that both name and age are required
        required = result.get("required", [])
        assert "name" in required
        assert "age" in required
        assert "email" in required

    def test_modify_schema_with_file_context(self, agent_client: AgentServerClient):
        """Test schema modification with document context."""

        # Original schema for a simple invoice
        original_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "Invoice identifier"},
                "total": {"type": "number", "description": "Total amount"},
            },
        }

        # Use train_ticket.pdf as context for modification
        file_name = "docs/train_ticket.pdf"

        # Modification instructions referencing the document
        instructions = (
            "Based on the document provided, add fields for journey details "
            "such as departure/arrival stations and travel date/time."
        )

        # Modify with file context
        result = agent_client.modify_schema(
            schema=original_schema, modification_instructions=instructions, file_name=file_name
        )

        # Basic assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("type") == "object"

        # TODO: These assertions are flaky because they check non-deterministic behavior
        # Original fields should still exist
        properties = result.get("properties", {})
        assert "invoice_number" in properties
        assert "total" in properties

    def test_modify_schema_string_input(self, agent_client: AgentServerClient):
        """Test that modify_schema accepts stringified JSON schema."""

        # Create schema as string
        original_schema_str = json.dumps(
            {"type": "object", "properties": {"id": {"type": "string"}}}
        )

        instructions = "Add a timestamp field of type string with ISO 8601 format"

        # Should accept string input
        result = agent_client.modify_schema(
            schema=original_schema_str, modification_instructions=instructions
        )

        assert result is not None
        assert isinstance(result, dict)
        assert "timestamp" in result.get("properties", {})


class TestModifySchema:
    """Test suite for schema modification functionality."""

    def test_modify_schema(
        self,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
        agent_server_client: AgentServerClient,
    ):
        """Test basic schema modification without file context."""

        # Create a sample schema to modify
        original_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's full name"},
                "age": {"type": "integer", "description": "Person's age in years"},
            },
            "required": ["name"],
        }
        # Modification instructions
        instructions = "Add an email field and make it required."
        updated_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's full name"},
                "age": {"type": "integer", "description": "Person's age in years"},
                "email": {"type": "string", "description": "Person's email address"},
            },
            "required": ["name", "email"],
        }

        # Set the mock response message
        mock_transport.prompts_generate_return_value = mock_response_message(
            json.dumps(updated_schema), "text"
        )

        # Modify the schema
        result = agent_server_client.modify_schema(
            schema=original_schema, modification_instructions=instructions
        )

        # Verify the result
        assert result is not None
        assert result == updated_schema
