from typing import Any
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import GenericDelta, combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.cortex.parsers import CortexParsers
from agent_platform.core.responses.content import (
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage


class TestCortexParsers:
    """Tests for the Cortex parsers."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parsers(self) -> CortexParsers:
        """Create Cortex parsers for testing."""
        return CortexParsers()

    @pytest.fixture
    def response_item(self) -> dict[str, Any]:
        """Fixture for creating a response item."""
        return {
            "choices": [
                {
                    "message": {
                        "content": "I'll help you evaluate this classic joke using the "
                        "joke_judge tool. I'll submit the complete joke as a single "
                        "string.",
                        "content_list": [
                            {
                                "type": "tool_use",
                                "tool_use": {
                                    "tool_use_id": "tooluse_jcKi9GD4SkajSgUYoujtXA",
                                    "name": "joke_judge",
                                    "input": {
                                        "joke": "Why did the chicken cross the road?",
                                    },
                                },
                            },
                        ],
                    },
                },
            ],
            "usage": {
                "prompt_tokens": 413,
                "completion_tokens": 66,
                "total_tokens": 479,
            },
        }

    @pytest.fixture
    def response_stream(self) -> list[str]:
        """Fixture for creating a sse response stream."""
        # Actual response sampled from curl request
        return [
            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content\":\"I'll\",\"content_list\":[{\"type\":\"text\","
            "\"text\":\"I'll\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content\":\" help you evaluate this classic\",\"content_list\":"
            "[{\"type\":\"text\",\"text\":\" help you evaluate this classic"
            "\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content\":\" joke using the joke_judge tool.\",\"content_list\":"
            "[{\"type\":\"text\",\"text\":\" joke using the joke_judge tool"
            ".\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content\":\" I'll submit the complete joke including both\""
            ",\"content_list\":[{\"type\":\"text\",\"text\":\" I'll submit the "
            "complete joke including both\"}]}}],\"usage\":{}}",

            # Insert an empty event (should get ignored)
            "",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content\":\" the setup and punchline.\",\"content_list\":"
            "[{\"type\":\"text\",\"text\":\" the setup and punchline."
            "\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"tool_use_id\":\"tooluse_jcKi9GD4SkajSgUYoujtXA\","
            "\"name\":\"joke_judge\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"{\\\"joke\\\": \\\"Wh\"}]}}],"
            "\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"y di\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"d the chick\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"en \"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"cross \"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"the road\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"? To get to \"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\"the other\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":"
            "{\"content_list\":[{\"input\":\" side!\\\"}\"}]}}],\"usage\":{}}",

            "data: {\"id\":\"08318161-92b0-40e7-a0c9-d66851104e0b\",\"model\""
            ":\"claude-3-5-sonnet\",\"choices\":[{\"delta\":{}}], \"usage\":{"
            "\"prompt_tokens\":413,\"completion_tokens\":66,\"total_tokens\":479}}",
        ]


    def test_parse_text_content(self, parsers: CortexParsers) -> None:
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

    def test_parse_tool_use_content(self, parsers: CortexParsers) -> None:
        """Test parsing tool use content."""
        tool_use_content = {
            "tool_use_id": "tool-1234",
            "name": "get_weather",
            "input": {"location": "New York"},
        }

        tool_use_content = parsers.parse_tool_use_content(tool_use_content)

        assert isinstance(tool_use_content, ResponseToolUseContent)
        assert tool_use_content.tool_call_id == "tool-1234"
        assert tool_use_content.tool_name == "get_weather"
        assert tool_use_content.tool_input == {"location": "New York"}
        assert tool_use_content.tool_input_raw == '{"location": "New York"}'

    def test_parse_content_item(self, parsers: CortexParsers) -> None:
        """Test parsing content items."""
        # Test with text content
        text_item = {"type": "text", "text": "Hello, world!"}
        content_item = parsers.parse_content_item(text_item)
        assert isinstance(content_item, ResponseTextContent)
        assert content_item.text == "Hello, world!"

        # Test with tool use content
        tool_use_item = {
            "type": "tool_use",
            "tool_use": {
                "tool_use_id": "tool-1234",
                "name": "get_weather",
                "input": {"location": "New York"},
            },
        }
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
        parsers: CortexParsers,
        response_item: dict[str, Any],
    ) -> None:
        """Test parsing a complete response."""
        response = parsers.parse_response(response_item)

        assert isinstance(response, ResponseMessage)
        assert response.role == "agent"
        assert len(response.content) == 2
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == (
            "I'll help you evaluate this classic joke using the "
            "joke_judge tool. I'll submit the complete joke as a single "
            "string."
        )
        assert isinstance(response.content[1], ResponseToolUseContent)
        assert response.content[1].tool_name == "joke_judge"
        assert response.content[1].tool_input == {
            "joke": "Why did the chicken cross the road?",
        }
        assert response.content[1].tool_input_raw == (
            '{"joke": "Why did the chicken cross the road?"}'
        )

    @pytest.mark.asyncio
    async def test_parse_stream_event(
        self,
        parsers: CortexParsers,
        response_stream: list[str],
    ) -> None:
        """Test parsing a stream event."""
        # Initialize message state
        message: dict[str, Any] = {}
        last_message: dict[str, Any] = {}

        deltas: list[GenericDelta] = []
        for line in response_stream:
            async for delta in parsers.parse_stream_event(
                line,
                message,
                last_message,
            ):
                deltas.append(delta)

        assert len(deltas) > 0

        combined = combine_generic_deltas(deltas)
        as_response = ResponseMessage.model_validate(combined)
        assert isinstance(as_response, ResponseMessage)
        assert as_response.role == "agent"
        assert len(as_response.content) == 2
        assert isinstance(as_response.content[0], ResponseTextContent)
        assert as_response.content[0].text == (
            "I'll help you evaluate this classic joke using the "
            "joke_judge tool. I'll submit the complete joke "
            "including both the setup and punchline."
        )
        assert isinstance(as_response.content[1], ResponseToolUseContent)
        assert as_response.content[1].tool_name == "joke_judge"
        assert as_response.content[1].tool_input == {
            "joke": "Why did the chicken cross the road?"
            " To get to the other side!",
        }
        assert as_response.content[1].tool_input_raw == (
            '{"joke": "Why did the chicken cross the road?'
            ' To get to the other side!"}'
        )
