"""Unit tests for the Google platform parsers."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.google.parsers import GoogleParsers
from agent_platform.core.responses.content.reasoning import ResponseReasoningContent
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage


class TestGoogleParsers:
    """Tests for the Google parsers."""

    @pytest.fixture
    def parsers(self) -> GoogleParsers:
        """Create a parser instance for testing."""
        return GoogleParsers()

    def test_parse_text_content(self, parsers: GoogleParsers) -> None:
        """Test parsing text content."""
        content = "Hello, world!"
        result = parsers.parse_text_content(content)

        assert isinstance(result, ResponseTextContent)
        assert result.text == "Hello, world!"

    def test_parse_tool_use_content(self, parsers: GoogleParsers) -> None:
        """Test parsing tool use content."""
        # Create a mock function call
        function_call = {
            "name": "test-tool",
            "args": {"key": "value"},
        }

        result = parsers.parse_tool_use_content(function_call, tool_call_id="test-id")

        assert isinstance(result, ResponseToolUseContent)
        assert result.tool_call_id == "test-id"
        assert result.tool_name == "test-tool"
        assert result.tool_input_raw == '{"key": "value"}'

    def test_parse_tool_use_content_generates_uuid(self, parsers: GoogleParsers) -> None:
        """Tool invocations without an id should fall back to a generated UUID."""
        expected_id = "12345678-1234-5678-1234-567812345678"
        with patch(
            "agent_platform.core.platforms.google.parsers.uuid.uuid4",
            return_value=expected_id,
        ):
            result = parsers.parse_tool_use_content(
                {"name": "tool-no-id", "args": {}},
                tool_call_id="",
            )

        assert result.tool_call_id == expected_id

    def test_parse_response_requires_candidates(self, parsers: GoogleParsers) -> None:
        """Responses that omit candidates should raise a ValueError."""
        from google.genai.types import GenerateContentResponse

        mock_response = MagicMock(spec=GenerateContentResponse)
        mock_response.candidates = []

        with pytest.raises(ValueError, match="No candidates"):
            parsers.parse_response(mock_response)

    def test_parse_response_requires_content(self, parsers: GoogleParsers) -> None:
        """Responses with empty candidate content should raise."""
        from google.genai.types import GenerateContentResponse

        candidate = MagicMock()
        candidate.content = None

        mock_response = MagicMock(spec=GenerateContentResponse)
        mock_response.candidates = [candidate]

        with pytest.raises(ValueError, match="No content"):
            parsers.parse_response(mock_response)

    def test_parse_response_includes_reasoning_content(self, parsers: GoogleParsers) -> None:
        """Reasoning parts should be converted into ResponseReasoningContent entries."""
        import base64

        from google.genai.types import GenerateContentResponse

        mock_part = MagicMock()
        mock_part.text = "chain of thought"
        mock_part.function_call = None
        mock_part.thought = True
        mock_part.thought_signature = b"\xde\xad\xbe\xef"

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        candidate = MagicMock()
        candidate.content = mock_content

        mock_response = MagicMock(spec=GenerateContentResponse)
        mock_response.candidates = [candidate]

        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 0
        usage_metadata.candidates_token_count = 0
        usage_metadata.total_token_count = 0
        usage_metadata.thoughts_token_count = 0
        mock_response.usage_metadata = usage_metadata

        response = parsers.parse_response(mock_response)
        assert isinstance(response.content[0], ResponseReasoningContent)
        expected_signature = base64.b64encode(b"\xde\xad\xbe\xef").decode("utf-8")
        assert response.content[0].signature == expected_signature

    def test_parse_response(self, parsers: GoogleParsers) -> None:
        """Test parsing a response."""
        # Mock a GenerateContentResponse
        from google.genai.types import GenerateContentResponse

        mock_response = MagicMock(spec=GenerateContentResponse)

        # Set up the candidates
        mock_part = MagicMock()
        mock_part.text = "Hello, world!"
        mock_part.function_call = None
        mock_part.thought = None
        mock_part.thought_signature = None

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response.candidates = [mock_candidate]

        # Set up usage_metadata
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 10
        mock_usage_metadata.candidates_token_count = 20
        mock_usage_metadata.total_token_count = 30
        mock_usage_metadata.thoughts_token_count = 5

        mock_response.usage_metadata = mock_usage_metadata

        # Parse the response
        result = parsers.parse_response(mock_response)

        assert isinstance(result, ResponseMessage)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ResponseTextContent)
        assert result.content[0].text == "Hello, world!"
        assert result.role == "agent"
        assert result.raw_response == mock_response
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20
        assert result.usage.total_tokens == 30
        assert "token_metrics" in result.metadata
        assert "thinking_tokens" in result.metadata["token_metrics"]
        assert result.metadata["token_metrics"]["thinking_tokens"] == 5

    def test_parse_response_with_tool_call(self, parsers: GoogleParsers) -> None:
        """Test parsing a response with tool call."""
        from google.genai.types import GenerateContentResponse

        # Mock a GenerateContentResponse with function call
        mock_response = MagicMock(spec=GenerateContentResponse)

        # Set up the function call
        mock_function_call = MagicMock()
        mock_function_call.name = "test-tool"
        mock_function_call.args = {"key": "value"}

        # Set up the part with function call
        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_function_call

        # Set up content and candidate
        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response.candidates = [mock_candidate]

        # Set up usage_metadata
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 10
        mock_usage_metadata.candidates_token_count = 20
        mock_usage_metadata.total_token_count = 30
        mock_usage_metadata.thoughts_token_count = 5

        mock_response.usage_metadata = mock_usage_metadata

        # Parse the response
        result = parsers.parse_response(mock_response)

        assert isinstance(result, ResponseMessage)
        assert len(result.content) == 1
        assert isinstance(result.content[0], ResponseToolUseContent)
        assert result.content[0].tool_name == "test-tool"
        assert result.content[0].tool_input["key"] == "value"
        assert result.role == "agent"
        assert result.raw_response == mock_response
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20
        assert result.usage.total_tokens == 30
        assert "token_metrics" in result.metadata
        assert "thinking_tokens" in result.metadata["token_metrics"]
        assert result.metadata["token_metrics"]["thinking_tokens"] == 5

    @pytest.mark.asyncio
    async def test_parse_stream_event(self, parsers: GoogleParsers) -> None:
        """Test parsing a stream event."""
        # Create mock stream event
        mock_event = MagicMock()

        # Set up the part with text
        mock_part = MagicMock()
        mock_part.text = "Hello, world!"
        mock_part.function_call = None
        mock_part.thought = None
        mock_part.thought_signature = None

        # Set up content and candidate
        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_event.candidates = [mock_candidate]

        # Set up usage_metadata
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 10
        mock_usage_metadata.candidates_token_count = 20
        mock_usage_metadata.total_token_count = 30
        mock_usage_metadata.thoughts_token_count = 5

        mock_event.usage_metadata = mock_usage_metadata

        # Initialize message state
        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }

        # Parse the stream event
        deltas = []
        async for delta in parsers.parse_stream_event(
            event=mock_event,
            message=message,
            last_message=last_message,
        ):
            deltas.append(delta)

        # Check that deltas were produced
        assert len(deltas) > 0
        assert all(isinstance(d, GenericDelta) for d in deltas)

        # Check the message content was updated
        assert len(message["content"]) > 0
        assert any(
            item.get("kind") == "text" and item.get("text") == "Hello, world!"
            for item in message["content"]
        )

        # Check token usage was added
        assert "usage" in message
        assert message["usage"]["input_tokens"] == 10
        assert message["usage"]["output_tokens"] == 20
        assert message["usage"]["total_tokens"] == 30

        # Check thinking tokens in metadata
        assert "metadata" in message
        assert "token_metrics" in message["metadata"]
        assert "thinking_tokens" in message["metadata"]["token_metrics"]
        assert message["metadata"]["token_metrics"]["thinking_tokens"] == 5

    @pytest.mark.asyncio
    async def test_parse_stream_event_tracks_modality_tokens(
        self,
        parsers: GoogleParsers,
    ) -> None:
        """Streaming metadata should capture modality-specific counts."""
        mock_event = MagicMock()
        mock_part = MagicMock()
        mock_part.text = ""
        mock_part.function_call = None
        mock_part.thought = None
        mock_part.thought_signature = None

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        mock_event.candidates = [mock_candidate]

        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 0
        usage_metadata.candidates_token_count = 0
        usage_metadata.total_token_count = 0
        usage_metadata.thoughts_token_count = 0

        detail = MagicMock()
        detail.modality = "TEXT"
        detail.token_count = 42
        usage_metadata.prompt_tokens_details = [detail]
        usage_metadata.candidates_tokens_details = None

        mock_event.usage_metadata = usage_metadata

        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }

        async for _ in parsers.parse_stream_event(mock_event, message, last_message):
            pass

        modality_tokens = message["metadata"]["token_metrics"]["modality_tokens"]
        assert modality_tokens == {"TEXT": 42}

    @pytest.mark.asyncio
    async def test_parse_stream_event_with_tool_call(
        self,
        parsers: GoogleParsers,
    ) -> None:
        """Test parsing a stream event with tool call."""
        # Create mock stream event with function call
        mock_event = MagicMock()

        # Set up function call
        mock_function_call = MagicMock()
        mock_function_call.name = "test-tool"
        mock_function_call.args = {"key": "value"}

        # Set up part with function call
        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_function_call
        mock_part.thought = None
        mock_part.thought_signature = None

        # Set up content and candidate
        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_event.candidates = [mock_candidate]

        # Set up usage_metadata
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 10
        mock_usage_metadata.candidates_token_count = 20
        mock_usage_metadata.total_token_count = 30
        mock_usage_metadata.thoughts_token_count = 5

        mock_event.usage_metadata = mock_usage_metadata

        # Initialize message state
        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }

        # Parse the stream event
        deltas = []
        async for delta in parsers.parse_stream_event(
            event=mock_event,
            message=message,
            last_message=last_message,
        ):
            deltas.append(delta)

        # Check that deltas were produced
        assert len(deltas) > 0
        assert all(isinstance(d, GenericDelta) for d in deltas)

        # Check tool use content was added
        assert len(message["content"]) > 0
        assert any(
            item.get("kind") == "tool_use" and item.get("tool_name") == "test-tool"
            for item in message["content"]
        )

    @pytest.mark.asyncio
    async def test_parse_stream_event_with_tool_call_thought_signature(
        self,
        parsers: GoogleParsers,
    ) -> None:
        """Tool calls with thought signatures should store base64-encoded strings."""
        import base64

        mock_event = MagicMock()

        mock_function_call = MagicMock()
        mock_function_call.name = "test-tool"
        mock_function_call.args = {"key": "value"}

        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_function_call
        mock_part.thought = None
        mock_part.thought_signature = b"\xde\xad\xbe\xef"

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_event.candidates = [mock_candidate]
        mock_event.usage_metadata = None

        message = {
            "role": "agent",
            "content": [],
            "additional_response_fields": {},
        }
        last_message = {"role": "agent", "content": [], "additional_response_fields": {}}

        async for _ in parsers.parse_stream_event(mock_event, message, last_message):
            pass

        tool_items = [item for item in message["content"] if item.get("kind") == "tool_use"]
        assert tool_items, "Expected tool use entry"
        expected_signature = base64.b64encode(b"\xde\xad\xbe\xef").decode("utf-8")
        assert tool_items[0]["metadata"]["thought_signature"] == expected_signature

    def test_extract_token_usage(self, parsers: GoogleParsers) -> None:
        """Test extracting token usage from a response."""
        # Create a mock response with token usage metadata
        from google.genai.types import GenerateContentResponse

        mock_response = MagicMock(spec=GenerateContentResponse)

        # Set up usage_metadata with different token count values
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 100
        mock_usage_metadata.candidates_token_count = 50
        mock_usage_metadata.total_token_count = 150
        mock_usage_metadata.thoughts_token_count = 25

        # Add token details by modality
        modal_token_count = MagicMock()
        modal_token_count.modality = "TEXT"
        modal_token_count.token_count = 100
        mock_usage_metadata.prompt_tokens_details = [modal_token_count]

        mock_response.usage_metadata = mock_usage_metadata

        # Call the method
        token_usage, thinking_tokens = parsers._extract_token_usage(mock_response)

        # Verify the results
        assert isinstance(token_usage, TokenUsage)
        assert token_usage.input_tokens == 100
        assert token_usage.output_tokens == 50
        assert token_usage.total_tokens == 150
        assert thinking_tokens == 25

    def test_extract_token_usage_handles_none_values(
        self,
        parsers: GoogleParsers,
    ) -> None:
        """Test extracting token usage when some values are None."""
        # Create a mock response with None values
        from google.genai.types import GenerateContentResponse

        mock_response = MagicMock(spec=GenerateContentResponse)

        # Set up usage_metadata with None values
        mock_usage_metadata = MagicMock()
        mock_usage_metadata.prompt_token_count = 100
        mock_usage_metadata.candidates_token_count = None
        mock_usage_metadata.total_token_count = None
        mock_usage_metadata.thoughts_token_count = None

        mock_response.usage_metadata = mock_usage_metadata

        # Call the method
        token_usage, thinking_tokens = parsers._extract_token_usage(mock_response)

        # Verify the results - should handle None values gracefully
        assert isinstance(token_usage, TokenUsage)
        assert token_usage.input_tokens == 100
        assert token_usage.output_tokens == 0  # None becomes 0
        assert token_usage.total_tokens == 100  # Uses input_tokens when total is None
        assert thinking_tokens == 0  # None becomes 0
