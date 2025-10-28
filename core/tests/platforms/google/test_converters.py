"""Unit tests for the Google platform converters."""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.google.converters import GoogleConverters
from agent_platform.core.platforms.google.prompts import GooglePrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class TestGoogleConverters:
    """Test converters for Google."""

    @pytest.fixture
    def converters(self) -> GoogleConverters:
        """Create a converter instance for testing."""
        return GoogleConverters()

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a kernel instance for testing."""
        return MagicMock(spec=Kernel)

    @pytest.mark.asyncio
    async def test_convert_text_content(self, converters: GoogleConverters) -> None:
        """Test converting text content."""
        content = PromptTextContent(text="Hello, world!")
        result = await converters.convert_text_content(content)

        assert isinstance(result, dict)
        assert "text" in result
        assert result["text"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_image_content(
        self,
        converters: GoogleConverters,
    ) -> None:
        """Test converting image content raises not implemented."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="http://example.com/image.jpg",
            sub_type="url",
        )

        with pytest.raises(NotImplementedError, match="Image not supported yet"):
            await converters.convert_image_content(content)

    @pytest.mark.asyncio
    async def test_convert_tool_use_content(self, converters: GoogleConverters) -> None:
        """Test converting tool use content."""
        # Create tool use content
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            tool_input_raw='{"key": "value"}',
        )

        # Convert it
        result = await converters.convert_tool_use_content(content)

        # Check the result
        assert isinstance(result, dict)
        assert "function_call" in result
        assert "name" in result["function_call"]
        assert result["function_call"]["name"] == "test-tool"
        assert "args" in result["function_call"]
        assert result["function_call"]["args"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_convert_tool_use_content_missing_name(
        self,
        converters: GoogleConverters,
    ) -> None:
        """Test converting tool use content with missing name."""
        # Create tool use content with empty name
        content = PromptToolUseContent(
            tool_call_id="test-tool-call-id",
            tool_name="",  # Empty name
            tool_input_raw='{"key": "value"}',
        )

        # Empty name is allowed in the current implementation
        # Let's just verify it works with empty name
        result = await converters.convert_tool_use_content(content)
        assert result["function_call"]["name"] == ""

    @pytest.mark.asyncio
    async def test_convert_tool_result_content(
        self,
        converters: GoogleConverters,
    ) -> None:
        """Test converting tool result content."""
        # Create tool result content
        content = PromptToolResultContent(
            tool_call_id="test-tool-call-id",
            tool_name="test-tool",
            content=[PromptTextContent(text="Hello, world!")],
        )

        # Convert it
        result = await converters.convert_tool_result_content(content)

        # Check the result
        assert isinstance(result, dict)
        assert "function_response" in result
        assert "name" in result["function_response"]
        assert result["function_response"]["name"] == "test-tool"
        assert "response" in result["function_response"]
        assert "content" in result["function_response"]["response"]
        assert result["function_response"]["response"]["content"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_convert_prompt(
        self,
        converters: GoogleConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt."""
        from google.genai.types import Content, Part

        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )

        # Create proper Content objects for testing
        mock_content1 = MagicMock(spec=Content)
        mock_content1.role = "user"
        mock_part1 = MagicMock(spec=Part)
        mock_part1.text = "Hello, world!"
        mock_content1.parts = [mock_part1]

        # Create system instruction content
        mock_system = MagicMock(spec=Content)
        mock_system.role = "user"
        mock_system_part = MagicMock(spec=Part)
        mock_system_part.text = "You are a helpful assistant."
        mock_system.parts = [mock_system_part]

        # Cast to proper types
        mock_messages = cast(list[Content], [mock_content1])

        with (
            patch.object(converters, "_convert_messages", return_value=mock_messages),
            patch.object(
                converters,
                "_convert_system_instruction",
                return_value=mock_system,
            ),
        ):
            # Attach kernel to converters
            converters.attach_kernel(kernel)

            # Finalize the prompt messages
            finalized_prompt = await prompt.finalize_messages(kernel)

            # Convert the prompt
            result = await converters.convert_prompt(
                finalized_prompt,
                model_id="gemini-1.5-pro",
            )

            # Check if the result is a GooglePrompt
            assert isinstance(result, GooglePrompt)
            assert len(result.contents) == 2  # System message + regular message

            # Check content structure - system message should be first
            assert result.contents[0].role == "user"
            assert result.contents[0].parts[0].text == "You are a helpful assistant."  # type: ignore
            assert result.contents[1].role == "user"
            assert result.contents[1].parts[0].text == "Hello, world!"  # type: ignore

    @pytest.mark.asyncio
    async def test_convert_prompt_with_tools(
        self,
        converters: GoogleConverters,
        kernel: Kernel,
    ) -> None:
        """Test converting a prompt with tools."""
        from google.genai import types
        from google.genai.types import Content, Part, Schema

        # Create empty schema for function declaration
        empty_schema = cast(Schema, {"type": "object", "properties": {}})

        # Create mock tool list with properly typed parameters
        function_declaration = types.FunctionDeclaration(
            name="test-tool",
            description="A test tool",
            parameters=empty_schema,
        )

        tool = types.Tool(
            function_declarations=[function_declaration],
        )

        mock_tools = [tool]

        # Create a test tool
        tool_definition = ToolDefinition(
            name="test-tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "A test key",
                    },
                },
                "required": ["key"],
            },
            function=lambda key: key,
        )

        # Create the prompt with a tool
        prompt = Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
            tools=[tool_definition],
        )

        # Create proper Content objects for testing
        mock_content1 = MagicMock(spec=Content)
        mock_content1.role = "user"
        mock_part1 = MagicMock(spec=Part)
        mock_part1.text = "Hello, world!"
        mock_content1.parts = [mock_part1]

        # Create system instruction content
        mock_system = MagicMock(spec=Content)
        mock_system.role = "user"
        mock_system_part = MagicMock(spec=Part)
        mock_system_part.text = "You are a helpful assistant."
        mock_system.parts = [mock_system_part]

        # Cast to proper types
        mock_messages = cast(list[Content], [mock_content1])

        # Mock the necessary methods
        with (
            patch.object(converters, "_convert_messages", return_value=mock_messages),
            patch.object(
                converters,
                "_convert_system_instruction",
                return_value=mock_system,
            ),
            patch.object(converters, "_convert_tools", return_value=mock_tools),
        ):
            # Attach kernel to converters
            converters.attach_kernel(kernel)

            # Finalize the prompt messages
            finalized_prompt = await prompt.finalize_messages(kernel)

            # Convert the prompt
            result = await converters.convert_prompt(
                finalized_prompt,
                model_id="gemini-1.5-pro",
            )

            # Check if the result is a GooglePrompt
            assert isinstance(result, GooglePrompt)
            # Safe access to tools - verify tools attribute exists and is not None
            assert hasattr(result, "tools")
            assert result.tools is not None
            # Compare tools when we know it's not None
            assert result.tools == mock_tools

    @pytest.mark.asyncio
    async def test_fix_schema_types(self, converters: GoogleConverters) -> None:
        """Test fixing schema types for Google."""
        # Test schema with various properties that need fixing
        test_schema = {
            "type": "object",
            "properties": {
                "string_prop": {"type": "string"},
                "int_prop": {"type": "integer"},
                "array_prop": {"type": "array", "items": {"type": "string"}},
                "object_prop": {
                    "type": "object",
                    "properties": {"nested": {"type": "string"}},
                },
            },
            "strict": True,
            "additionalProperties": False,
            "required": ["string_prop"],
        }

        # Fix the schema
        fixed_schema = converters._fix_schema_types(test_schema)

        # Verify fields were removed/fixed
        assert "strict" not in fixed_schema
        assert "additionalProperties" not in fixed_schema
        assert fixed_schema["type"] == "object"
        assert len(fixed_schema["properties"]) == 4  # All properties kept
        assert fixed_schema["required"] == ["string_prop"]
