"""
Unit tests for schema generation functionality.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.agent_server_client.transport.base import ResponseMessage
from sema4ai_docint.utils import validate_extraction_schema
from tests.agent_server_client.conftest import MockTransport


@pytest.mark.schema_eval
class TestEvalSchemaGeneration:
    """Test schema generation functionality."""

    def test_generate_schema(self, agent_client: AgentServerClient):
        """Test schema generation from document."""

        # Use train_ticket.pdf as the test file
        file_name = "docs/train_ticket.pdf"

        # Generate schema from document
        result = agent_client.generate_schema(file_name)

        # Basic assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("type") == "object"
        assert result.get("properties") is not None

    def test_agent_response_to_error_feedback_in_retry_attempt(
        self, agent_client: AgentServerClient
    ):
        """Test that agent can correct errors when given exact error feedback from retry logic."""

        # Get the path to the test PDF file directly
        doc_path = Path(__file__).parent / "test-data" / "docs" / "train_ticket.pdf"

        # Get images from the PDF
        images = agent_client._pdf_to_images(doc_path)

        # Build chat content step by step with images
        chat_content = []

        # Add initial user request
        chat_content.append(
            {
                "kind": "text",
                "text": (
                    "Please generate a JSON Schema from the document represented by these images. "
                    "Do not include comment characters in the JSONSchema. Do use the 'description' "
                    "field to describe the field."
                ),
            }
        )

        # Add the images from the PDF
        chat_content.extend(images)

        # Simulate bad agent response with JSON syntax errors
        bad_json = """
                    {
            // Defines the structure for a basic train ticket record
            "type": "object",
            "properties": {
                // Unique Passenger Name Record assigned after booking
                "pnr": { "type": "string" },  // used to fetch ticket status later

                // Code representing the train (e.g., 12951 for Rajdhani Express)
                "train_number": { "type": "string" }  // mandatory for identifying the service

                // List of all travelers included in the booking
                "passengers": {
                "type": "array",
                "items": {
                    // Each passenger entry in the list
                    "type": "object",
                    "properties": {
                    "name": { "type": "string" },  // full name as printed on ticket
                    "age": { "type": "integer" }  // used for fare category and berth allocation
                    },
                    "required": ["name", "age"]
                }
                },

                // Total amount charged for the booking including taxes
                "total_fare": { "type": "number"  // expressed in INR
            },
            "required": [
                "pnr",
                "train_number"  // essential for identification
                "passengers",  // must have at least one traveler
                "total_fare"
            ]
        """

        # Generate error feedback as retry logic would
        try:
            json.loads(bad_json)
        except json.JSONDecodeError as e:
            error_feedback = (
                f"Previous response was not valid JSON. Error: {e!s}. Please "
                f"provide valid JSON without markdown formatting."
            )

        # Add error feedback to chat
        chat_content.append({"kind": "text", "text": error_feedback})

        # Send chat with error feedback
        payload = {
            "prompt": {
                "messages": [{"role": "user", "content": chat_content}],
                "tools": [],
                "temperature": 0.7,
                "max_output_tokens": 10240,
            },
        }

        response = agent_client.transport.prompts_generate(payload)

        # Extract and clean response
        from sema4ai_docint.agent_server_client.client import _trim_json_markup

        response_text = agent_client.extract_text_content(response)
        clean_text = _trim_json_markup(response_text)

        # Verify agent corrected the error
        try:
            schema = json.loads(clean_text)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Agent failed to correct JSON error. Response: {clean_text[:200]}... Error: {e}"
            )

        # validate_extraction_schema will raise an error if the schema is invalid
        _ = validate_extraction_schema(schema)


class TestSchemaGeneration:
    """Unit tests for schema generation using mocked transport."""

    def test_generate_schema_with_user_prompt(
        self,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
        agent_server_client_with_mocked_file_content: AgentServerClient,
    ) -> None:
        """Test schema generation with additional user instructions."""

        agent_server_client = agent_server_client_with_mocked_file_content

        generated_schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "number"},
            },
            "required": ["invoice_number", "total"],
        }

        # Set the mock response message
        mock_transport.prompts_generate_return_value = mock_response_message(
            json.dumps(generated_schema), "text"
        )

        user_prompt = "Focus on invoice totals and due dates."

        result = agent_server_client.generate_schema(
            file_name="docs/sample.pdf",
            user_prompt=user_prompt,
        )

        captured_payloads = mock_transport.captured_prompt_generate_payloads

        assert result == generated_schema
        assert captured_payloads, "Expected generate_schema to send at least one payload"

        prompt_content = captured_payloads[0]["prompt"]["messages"][0]["content"]
        instructions_text = [
            block["text"] for block in prompt_content if block.get("kind") == "text"
        ]
        assert any("Additional instructions" in text for text in instructions_text)
        assert any(user_prompt in text for text in instructions_text)

    def test_generate_schema_with_reserved_keyword(
        self,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
        agent_server_client_with_mocked_file_content: AgentServerClient,
    ):
        """Test that generate_schema rejects a schema with a reserved keyword."""

        agent_server_client = agent_server_client_with_mocked_file_content

        reserved_schema = {
            "type": "object",
            "properties": {
                "select": {"type": "string"},
            },
            "required": ["select"],
        }

        corrected_schema = {
            "type": "object",
            "properties": {
                "selected_value": {"type": "string"},
            },
            "required": ["selected_value"],
        }

        mock_transport.set_prompts_generate_responses(
            [
                mock_response_message(json.dumps(reserved_schema), "text"),
                mock_response_message(json.dumps(corrected_schema), "text"),
            ]
        )

        result = agent_server_client.generate_schema(file_name="docs/sample.pdf")

        assert result == corrected_schema

        captured_payloads = mock_transport.captured_prompt_generate_payloads
        assert len(captured_payloads) == 2

        second_attempt_messages = captured_payloads[1]["prompt"]["messages"][0]["content"]
        error_texts = [
            block["text"] for block in second_attempt_messages if block.get("kind") == "text"
        ]
        assert any("reserved SQL keyword" in text for text in error_texts)
        assert any("select" in text for text in error_texts)
