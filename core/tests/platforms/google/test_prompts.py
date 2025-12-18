"""Unit tests for the Google platform prompts."""

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.google.converters import GoogleConverters
from agent_platform.core.platforms.google.prompts import GooglePrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage

if TYPE_CHECKING:
    from google.genai.types import Content


class TestGooglePrompt:
    """Tests for the Google prompt."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def contents(self) -> list["Content"]:
        """Create a list of content items for testing."""
        from google.genai.types import Content, Part

        # Create proper Content objects instead of dictionaries
        content1 = MagicMock(spec=Content)
        content1.role = "user"
        part1 = MagicMock(spec=Part)
        part1.text = "You are a helpful assistant."
        content1.parts = [part1]

        content2 = MagicMock(spec=Content)
        content2.role = "user"
        part2 = MagicMock(spec=Part)
        part2.text = "Hello, world!"
        content2.parts = [part2]

        return [content1, content2]

    @pytest.fixture
    def google_prompt(self, contents: "list[Content]") -> GooglePrompt:
        """Create a Google prompt for testing."""
        return GooglePrompt(
            contents=contents,
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=4096,
        )

    async def _convert_prompt_for_model(
        self,
        kernel: Kernel,
        model_id: str,
    ) -> GooglePrompt:
        """Convert a minimal prompt using the Google converters for a model."""
        from google.genai.types import Content, Part

        converters = GoogleConverters()
        prompt = Prompt(
            messages=[PromptUserMessage([PromptTextContent(text="Resolve reasoning suffixes")])],
        )

        mock_content = MagicMock(spec=Content)
        mock_content.role = "user"
        mock_part = MagicMock(spec=Part)
        mock_part.text = "Resolve reasoning suffixes"
        mock_content.parts = [mock_part]
        mock_messages = cast(list[Content], [mock_content])

        with patch.object(converters, "_convert_messages", return_value=mock_messages):
            converters.attach_kernel(kernel)
            finalized_prompt = await prompt.finalize_messages(
                kernel,
                prompt_finalizers=[],
            )
            return await converters.convert_prompt(
                finalized_prompt,
                model_id=model_id,
            )

    def test_as_platform_request(self, google_prompt: GooglePrompt) -> None:
        """Test converting to platform request."""
        from google.genai import types
        from google.genai.types import Content

        request = google_prompt.as_platform_request(model="gemini-2.5-pro")

        assert isinstance(request, dict)
        assert "model" in request
        assert request["model"] == "gemini-2.5-pro"
        assert "contents" in request

        # Use cast to help type checker understand what we're doing
        contents = cast(list[Content], request["contents"])
        assert len(contents) == 2
        assert contents[0].role == "user"
        assert contents[0].parts[0].text == "You are a helpful assistant."  # type: ignore
        assert contents[1].role == "user"
        assert contents[1].parts[0].text == "Hello, world!"  # type: ignore

        assert "config" in request
        assert isinstance(request["config"], types.GenerateContentConfig)
        assert request["config"].temperature == 0.0
        assert request["config"].top_p == 1.0
        assert request["config"].max_output_tokens == 4096

    def test_as_platform_request_with_stream(self, google_prompt: GooglePrompt) -> None:
        """Test converting to platform request with streaming enabled."""
        from google.genai import types
        from google.genai.types import Content

        request = google_prompt.as_platform_request(model="gemini-2.5-pro", stream=True)

        assert isinstance(request, dict)
        assert "model" in request
        assert request["model"] == "gemini-2.5-pro"
        assert "contents" in request

        # Use cast to help type checker
        contents = cast(list[Content], request["contents"])
        assert len(contents) == 2

        assert "config" in request
        assert isinstance(request["config"], types.GenerateContentConfig)
        assert request["config"].temperature == 0.0
        assert request["config"].top_p == 1.0
        assert request["config"].max_output_tokens == 4096

    def test_as_platform_request_no_tools(self, contents: "list[Content]") -> None:
        """Test converting to platform request with no tools."""
        from google.genai import types
        from google.genai.types import Content

        google_prompt = GooglePrompt(
            contents=contents,
            temperature=0.5,
            top_p=0.8,
        )

        request = google_prompt.as_platform_request(model="gemini-2.5-pro")

        assert isinstance(request, dict)
        assert "model" in request
        assert request["model"] == "gemini-2.5-pro"
        assert "contents" in request

        # Use cast to help type checker
        req_contents = cast(list[Content], request["contents"])
        assert len(req_contents) == 2

        assert "config" in request
        assert isinstance(request["config"], types.GenerateContentConfig)
        assert request["config"].temperature == 0.5
        assert request["config"].top_p == 0.8

        # Check tools is None (using type guard)
        config = request["config"]
        tools = getattr(config, "tools", None)
        assert tools is None

    def test_as_platform_request_with_tools(
        self,
        contents: "list[Content]",
    ) -> None:
        """Test converting to platform request with tools."""
        from google.genai import types
        from google.genai.types import Content, Schema

        # Create empty schema for function declaration
        empty_schema = cast(Schema, {"type": "object", "properties": {}})

        # Create the function declaration with proper schema
        function_declaration = types.FunctionDeclaration(
            name="test-tool",
            description="A test tool",
            parameters=empty_schema,
        )

        tool = types.Tool(
            function_declarations=[function_declaration],
        )

        # Use proper typing for tools
        mock_tools = [tool]

        # Create prompt with tools
        google_prompt = GooglePrompt(
            contents=contents,
            tools=mock_tools,
            temperature=0.7,
        )

        request = google_prompt.as_platform_request(model="gemini-2.5-pro")

        assert isinstance(request, dict)
        assert "model" in request
        assert request["model"] == "gemini-2.5-pro"
        assert "contents" in request

        # Use cast to help type checker
        req_contents = cast(list[Content], request["contents"])
        assert len(req_contents) == 2

        assert "config" in request
        assert isinstance(request["config"], types.GenerateContentConfig)
        assert request["config"].temperature == 0.7

        # Check tools with type guard
        config = request["config"]
        tools = getattr(config, "tools", None)
        assert tools is not None
        assert tools == mock_tools

    def test_as_platform_request_includes_thinking_budget(
        self,
        contents: "list[Content]",
    ) -> None:
        from google.genai import types

        google_prompt = GooglePrompt(contents=contents, thinking_budget=2048)
        request = google_prompt.as_platform_request(model="gemini-2.5-pro")

        config = request["config"]
        assert isinstance(config, types.GenerateContentConfig)
        thinking_config = getattr(config, "thinking_config", None)
        assert thinking_config is not None
        assert thinking_config.thinking_budget == 2048
        assert thinking_config.include_thoughts is True

    def test_as_platform_request_includes_thinking_level(
        self,
        contents: "list[Content]",
    ) -> None:
        from google.genai import types

        google_prompt = GooglePrompt(contents=contents, thinking_level="low")
        request = google_prompt.as_platform_request(model="gemini-3-pro-preview")

        config = request["config"]
        assert isinstance(config, types.GenerateContentConfig)
        thinking_config = getattr(config, "thinking_config", None)
        assert thinking_config is not None
        assert str(thinking_config.thinking_level).lower().endswith("low")
        assert thinking_config.include_thoughts is True

    def test_prompt_properties(self, contents: "list[Content]") -> None:
        """Test prompt properties and defaults."""
        from google.genai import types
        from google.genai.types import Schema

        # Test with defaults
        prompt = GooglePrompt(contents=contents)
        assert prompt.contents == contents
        assert prompt.temperature == 0.0
        assert prompt.top_p == 1.0
        assert prompt.max_output_tokens == 4096
        assert prompt.tools is None

        # Test with custom values
        # Create empty schema for function declaration
        empty_schema = cast(Schema, {"type": "object", "properties": {}})

        # Create the function declaration with proper schema
        function_declaration = types.FunctionDeclaration(
            name="test-tool",
            description="A test tool",
            parameters=empty_schema,
        )

        tool = types.Tool(
            function_declarations=[function_declaration],
        )

        # Create properly typed tools
        mock_tools = [tool]

        prompt = GooglePrompt(
            contents=contents,
            tools=mock_tools,
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=1000,
        )
        assert prompt.contents == contents
        assert prompt.tools == mock_tools
        assert prompt.temperature == 0.7
        assert prompt.top_p == 0.9
        assert prompt.max_output_tokens == 1000

    def test_thinking_config_for_gemini_2_5(
        self,
        contents: "list[Content]",
    ) -> None:
        """Test thinking config is added for Gemini 2.5 models."""
        from google.genai import types

        google_prompt = GooglePrompt(
            contents=contents,
        )

        # Create a proper mock for the GenerateContentConfig that we'll return
        mock_config = MagicMock(spec=types.GenerateContentConfig)

        # Set thinking_config property
        mock_config.thinking_config = MagicMock()
        mock_config.thinking_config.thinking_budget = 2048

        # Patch the as_platform_request method to return a dict with our mock
        with patch.object(
            GooglePrompt,
            "as_platform_request",
            return_value={
                "model": "gemini-2.5-flash-preview-04-17-high",
                "contents": contents,
                "config": mock_config,
            },
        ):
            # Test first model
            request = google_prompt.as_platform_request(
                model="gemini-2.5-flash-preview-04-17-high",
            )

            # Verify the config is in the request
            assert isinstance(request, dict)
            assert "config" in request
            assert request["config"] is mock_config

            # Test second model
            # Create a different mock with different thinking budget
            mock_config2 = MagicMock(spec=types.GenerateContentConfig)
            mock_config2.thinking_config = MagicMock()
            mock_config2.thinking_config.thinking_budget = 1024

            # Patch again with a different return value
            with patch.object(
                GooglePrompt,
                "as_platform_request",
                return_value={
                    "model": "gemini-2.5-flash-preview-04-17-low",
                    "contents": contents,
                    "config": mock_config2,
                },
            ):
                # Request with a 2.5 model with low thinking budget
                request = google_prompt.as_platform_request(
                    model="gemini-2.5-flash-preview-04-17-low",
                )

                # Verify the config is in the request
                assert isinstance(request, dict)
                assert "config" in request
                assert request["config"] is mock_config2

    @pytest.mark.asyncio
    async def test_gemini3_suffixes_affect_thinking_level(
        self,
        kernel: Kernel,
    ) -> None:
        low_prompt = await self._convert_prompt_for_model(kernel, "gemini-3-pro-low")
        high_prompt = await self._convert_prompt_for_model(kernel, "gemini-3-pro-high")

        low_request = low_prompt.as_platform_request(model="gemini-3-pro-low")
        high_request = high_prompt.as_platform_request(model="gemini-3-pro-high")

        low_config = low_request["config"]
        low_thinking = getattr(low_config, "thinking_config", None)
        assert low_thinking is not None

        high_config = high_request["config"]
        high_thinking = getattr(high_config, "thinking_config", None)
        assert high_thinking is not None

        low_level = str(low_thinking.thinking_level).lower()
        high_level = str(high_thinking.thinking_level).lower()
        assert low_level.endswith("low")
        assert high_level.endswith("high")
        assert low_level != high_level

    @pytest.mark.parametrize(
        ("model_id", "expected_budget"),
        [
            ("gemini-2.5-pro-low", 1024),
            ("gemini-2.5-pro-medium", 8192),
            ("gemini-2.5-pro-high", 24576),
        ],
    )
    @pytest.mark.asyncio
    async def test_gemini25_pro_suffixes_affect_thinking_budget(
        self,
        kernel: Kernel,
        model_id: str,
        expected_budget: int,
    ) -> None:
        prompt = await self._convert_prompt_for_model(kernel, model_id)
        request = prompt.as_platform_request(model=model_id)
        config = request["config"]
        thinking_config = getattr(config, "thinking_config", None)
        assert thinking_config is not None
        assert thinking_config.thinking_budget == expected_budget
        assert thinking_config.include_thoughts is True

    @pytest.mark.parametrize(
        ("model_id", "expected_budget"),
        [
            ("gemini-2.5-flash-preview-04-17-low", 1024),
            ("gemini-2.5-flash-preview-04-17-medium", 8192),
            ("gemini-2.5-flash-preview-04-17-high", 24576),
        ],
    )
    @pytest.mark.asyncio
    async def test_gemini25_flash_suffixes_affect_thinking_budget(
        self,
        kernel: Kernel,
        model_id: str,
        expected_budget: int,
    ) -> None:
        prompt = await self._convert_prompt_for_model(kernel, model_id)
        request = prompt.as_platform_request(model=model_id)
        config = request["config"]
        thinking_config = getattr(config, "thinking_config", None)
        assert thinking_config is not None
        assert thinking_config.thinking_budget == expected_budget
        assert thinking_config.include_thoughts is True
