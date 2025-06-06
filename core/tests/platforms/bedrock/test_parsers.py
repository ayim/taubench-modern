from typing import Any
from unittest.mock import MagicMock

import pytest

# Import types for type checking only
from types_boto3_bedrock_runtime.type_defs import (
    ConverseResponseTypeDef,
    ConverseStreamResponseTypeDef,
)

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.parsers import BedrockParsers
from agent_platform.core.responses.content import (
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage


class TestBedrockParsers:
    """Tests for the Bedrock parsers."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parsers(self) -> BedrockParsers:
        """Create Bedrock parsers for testing."""
        return BedrockParsers()

    @pytest.fixture
    def response_item(self) -> ConverseResponseTypeDef:
        """Fixture for creating a response item."""
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockOutputTypeDef,
            ConverseMetricsTypeDef,
            ConverseOutputTypeDef,
            ConverseResponseTypeDef,
            MessageOutputTypeDef,
            ResponseMetadataTypeDef,
            TokenUsageTypeDef,
            ToolUseBlockOutputTypeDef,
        )

        return ConverseResponseTypeDef(
            output=ConverseOutputTypeDef(
                message=MessageOutputTypeDef(
                    role="assistant",
                    content=[
                        ContentBlockOutputTypeDef(
                            text="I'll check the weather for you.",
                        ),
                        ContentBlockOutputTypeDef(
                            toolUse=ToolUseBlockOutputTypeDef(
                                toolUseId="tool-1234",
                                name="get_weather",
                                input={"location": "New York"},
                            ),
                        ),
                    ],
                ),
            ),
            stopReason="tool_use",
            usage=TokenUsageTypeDef(
                inputTokens=10,
                outputTokens=20,
                totalTokens=30,
            ),
            metrics=ConverseMetricsTypeDef(latencyMs=500),
            additionalModelResponseFields={},
            trace={},
            performanceConfig={},
            ResponseMetadata=ResponseMetadataTypeDef(
                RequestId="test-request-id",
                HTTPStatusCode=200,
                HTTPHeaders={},
                RetryAttempts=0,
            ),
        )

    @pytest.fixture
    def stream_item(self) -> ConverseStreamResponseTypeDef:
        """Fixture for creating a mock stream item."""
        from botocore.eventstream import EventStream
        from types_boto3_bedrock_runtime.type_defs import (
            ConverseStreamOutputTypeDef,
            ConverseStreamResponseTypeDef,
            ResponseMetadataTypeDef,
        )

        # Mock the EventStream to yield a sequence of
        # ConverseStreamOutputTypeDef instances
        def mock_event_stream():
            yield ConverseStreamOutputTypeDef()
            # Add more yields if multiple events are needed

        # Create a MagicMock for the EventStream
        mock_stream = MagicMock(spec=EventStream)
        mock_stream.__iter__.side_effect = mock_event_stream

        # Construct the ConverseStreamResponseTypeDef with the mocked EventStream
        return ConverseStreamResponseTypeDef(
            stream=mock_stream,
            ResponseMetadata=ResponseMetadataTypeDef(
                RequestId="test-request-id",
                HTTPStatusCode=200,
                HTTPHeaders={},
                RetryAttempts=0,
            ),
        )

    def test_parse_text_content(self, parsers: BedrockParsers) -> None:
        """Test parsing text content."""
        # Test with dict
        text_dict = {"type": "text", "text": "Hello, world!"}
        text_content = parsers.parse_text_content(text_dict)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

        # Test with string
        text_str = "Hello, world!"
        text_content = parsers.parse_text_content(text_str)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

        # Test with bytes
        text_bytes = b"Hello, world!"
        text_content = parsers.parse_text_content(text_bytes)
        assert isinstance(text_content, ResponseTextContent)
        assert text_content.text == "Hello, world!"

    def test_parse_tool_use_content(self, parsers: BedrockParsers) -> None:
        """Test parsing tool use content."""
        from types_boto3_bedrock_runtime.type_defs import ToolUseBlockTypeDef

        tool_use_content = ToolUseBlockTypeDef(
            toolUseId="tool-1234",
            name="get_weather",
            input={"location": "New York"},
        )

        tool_use_content = parsers.parse_tool_use_content(tool_use_content)

        assert isinstance(tool_use_content, ResponseToolUseContent)
        assert tool_use_content.tool_call_id == "tool-1234"
        assert tool_use_content.tool_name == "get_weather"
        assert tool_use_content.tool_input == {"location": "New York"}
        assert tool_use_content.tool_input_raw == '{"location": "New York"}'

    def test_parse_content_item(self, parsers: BedrockParsers) -> None:
        """Test parsing content items."""
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockTypeDef,
            ToolUseBlockTypeDef,
        )

        # Test with text content
        text_item = ContentBlockTypeDef(text="Hello, world!")
        content_item = parsers.parse_content_item(text_item)
        assert isinstance(content_item, ResponseTextContent)
        assert content_item.text == "Hello, world!"

        # Test with tool use content
        tool_use_item = ContentBlockTypeDef(
            toolUse=ToolUseBlockTypeDef(
                toolUseId="tool-1234",
                name="get_weather",
                input={"location": "New York"},
            ),
        )
        content_item = parsers.parse_content_item(tool_use_item)
        assert isinstance(content_item, ResponseToolUseContent)
        assert content_item.tool_call_id == "tool-1234"
        assert content_item.tool_name == "get_weather"

        # Test with unsupported content type
        with pytest.raises(
            ValueError,
            match="Unsupported content type in item:",
        ):
            parsers.parse_content_item(
                {"type": "unsupported"},  # type: ignore (we're testing bad input)
            )

    def test_parse_response(
        self,
        parsers: BedrockParsers,
        response_item: ConverseResponseTypeDef,
    ) -> None:
        """Test parsing a complete response."""
        response = parsers.parse_response(response_item)

        assert isinstance(response, ResponseMessage)
        assert response.role == "agent"
        assert len(response.content) == 2
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "I'll check the weather for you."
        assert isinstance(response.content[1], ResponseToolUseContent)
        assert response.content[1].tool_name == "get_weather"

    @pytest.mark.asyncio
    async def test_parse_stream_event(
        self,
        parsers: BedrockParsers,
        stream_item: ConverseStreamResponseTypeDef,
    ) -> None:
        """Test parsing a stream event."""
        # Initialize message state
        message: dict[str, Any] = {}
        last_message: dict[str, Any] = {}

        # Test message start
        message_start_event = {
            "messageStart": {"role": "assistant"},
        }
        deltas = []
        async for delta in parsers.parse_stream_event(
            message_start_event,
            stream_item,
            message,
            last_message,
        ):
            deltas.append(delta)

        assert len(deltas) > 0
        assert message.get("role") == "agent"
