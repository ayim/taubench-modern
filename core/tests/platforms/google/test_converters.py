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
    PromptReasoningContent,
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

        assert hasattr(result, "text")
        assert result.text == "Hello, world!"

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
        assert hasattr(result, "function_call")
        assert result.function_call is not None
        assert result.function_call.name == "test-tool"
        assert result.function_call.args == {"key": "value"}

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
        assert result.function_call is not None
        assert result.function_call.name == ""

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
        assert hasattr(result, "function_response")
        assert result.function_response is not None
        assert result.function_response.name == "test-tool"
        assert result.function_response.response is not None
        assert result.function_response.response["content"] == "Hello, world!"

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
    async def test_convert_prompt_sets_thinking_budget(
        self,
        converters: GoogleConverters,
        kernel: Kernel,
    ) -> None:
        from google.genai.types import Content, Part

        prompt = Prompt(
            messages=[PromptUserMessage([PromptTextContent(text="Hello, world!")])],
        )

        mock_content = MagicMock(spec=Content)
        mock_content.role = "user"
        mock_part = MagicMock(spec=Part)
        mock_part.text = "Hello, world!"
        mock_content.parts = [mock_part]

        mock_messages = cast(list[Content], [mock_content])

        with patch.object(converters, "_convert_messages", return_value=mock_messages):
            converters.attach_kernel(kernel)
            finalized_prompt = await prompt.finalize_messages(kernel)
            result = await converters.convert_prompt(
                finalized_prompt, model_id="gemini-2.5-pro-high"
            )

        assert result.thinking_budget == 24576
        assert result.thinking_level is None

    @pytest.mark.asyncio
    async def test_convert_prompt_sets_thinking_level_for_gemini3(
        self,
        converters: GoogleConverters,
        kernel: Kernel,
    ) -> None:
        from google.genai.types import Content, Part

        prompt = Prompt(
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )

        mock_content = MagicMock(spec=Content)
        mock_content.role = "user"
        mock_part = MagicMock(spec=Part)
        mock_part.text = "Hi"
        mock_content.parts = [mock_part]

        mock_messages = cast(list[Content], [mock_content])

        with patch.object(converters, "_convert_messages", return_value=mock_messages):
            converters.attach_kernel(kernel)
            finalized_prompt = await prompt.finalize_messages(kernel)
            result = await converters.convert_prompt(
                finalized_prompt,
                model_id="gemini-3-pro-preview",
            )

        assert result.thinking_level == "high"
        assert result.thinking_budget == 0

        prompt_min = Prompt(
            minimize_reasoning=True,
            messages=[PromptUserMessage([PromptTextContent(text="Hi")])],
        )
        with patch.object(converters, "_convert_messages", return_value=mock_messages):
            converters.attach_kernel(kernel)
            finalized_prompt = await prompt_min.finalize_messages(kernel)
            result_low = await converters.convert_prompt(
                finalized_prompt,
                model_id="gemini-3-pro-preview",
            )

        assert result_low.thinking_level == "low"

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
    async def test_process_message_content_includes_reasoning(
        self,
        converters: GoogleConverters,
    ) -> None:
        """Reasoning content should be converted with thought metadata."""
        contents = [
            PromptTextContent(text="visible output"),
            PromptReasoningContent(reasoning="internal", signature="deadbeef"),
        ]

        parts = await converters._process_message_content(contents)

        assert len(parts) == 2
        reasoning_parts = [part for part in parts if getattr(part, "thought", False)]
        assert reasoning_parts, "Expected at least one reasoning part"
        assert reasoning_parts[0].text == "internal"
        assert reasoning_parts[0].thought_signature.hex() == "deadbeef"  # type: ignore[attr-defined]

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

    @pytest.mark.asyncio
    async def test_convert_prompt_minimize_reasoning_clamps_budget(
        self,
        converters: GoogleConverters,
        kernel: Kernel,
    ) -> None:
        """Minimize reasoning should dial Gemini Pro budgets down to minimum."""
        prompt = Prompt(
            minimize_reasoning=True,
            messages=[PromptUserMessage([PromptTextContent(text="Hello")])],
        )

        converters.attach_kernel(kernel)
        finalized_prompt = await prompt.finalize_messages(kernel)
        result = await converters.convert_prompt(
            finalized_prompt,
            model_id="gemini-2.5-pro-high",
        )

        assert result.thinking_budget == 1024
        assert result.thinking_level is None

    def test_create_schema_from_param_types_handles_union_types(
        self,
        converters: GoogleConverters,
    ) -> None:
        """Fallback schema generation should mark optional params as nullable."""
        tool = ToolDefinition(
            name="fallback-tool",
            description="",
            input_schema={},
        )
        object.__setattr__(  # type: ignore[misc]
            tool,
            "_parameter_types",
            {
                "maybe": str | None,
                "count": int,
            },
        )

        schema = converters._create_schema_from_param_types(tool)

        assert schema["properties"]["maybe"]["type"] == "string"
        assert schema["properties"]["maybe"]["nullable"] is True
        assert schema["properties"]["count"]["type"] == "integer"
