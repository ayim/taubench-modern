import json
from collections.abc import AsyncGenerator
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.base import (
    PlatformClient,
    PlatformConfigs,
    PlatformConverters,
    PlatformParameters,
    PlatformParsers,
    PlatformPrompt,
)
from agent_platform.core.prompts import (
    Prompt,
    PromptAudioContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.content import PromptDocumentContent
from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage


# Mock implementations for testing
class MockPlatformPrompt(PlatformPrompt):
    """A mock platform prompt for testing."""

    def as_platform_request(self, model: str, stream: bool = False) -> dict[str, Any]:
        """Convert the prompt to a mock platform request."""
        return {"model": model, "stream": stream, "messages": []}


class MockPlatformParameters(PlatformParameters):
    """A mock platform parameters for testing."""

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
    ) -> dict:
        """Convert parameters to a dictionary."""
        return {"api_key": "mock_api_key"}


class MockPlatformConverters(PlatformConverters):
    """Mock converters for testing."""

    async def convert_text_content(self, content: PromptTextContent) -> dict:
        """Mock convert text content."""
        return {"type": "text", "text": content.text}

    async def convert_image_content(self, content: PromptImageContent) -> dict:
        """Mock convert image content."""
        return {
            "type": "image",
            "mime_type": content.mime_type,
            "value": content.value,
        }

    async def convert_audio_content(self, content: PromptAudioContent) -> dict:
        """Mock convert audio content."""
        return {
            "type": "audio",
            "mime_type": content.mime_type,
            "value": content.value,
        }

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> dict:
        """Mock convert tool use content."""
        return {
            "type": "tool_use",
            "tool_call_id": content.tool_call_id,
            "tool_name": content.tool_name,
        }

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> dict:
        """Mock convert tool result content."""
        return {
            "type": "tool_result",
            "tool_call_id": content.tool_call_id,
            "tool_name": content.tool_name,
        }

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> dict:
        """Mock convert document content."""
        return {
            "type": "document",
            "mime_type": content.mime_type,
            "value": content.value,
            "name": content.name,
        }

    async def convert_prompt(self, prompt: Prompt) -> MockPlatformPrompt:
        """Mock convert prompt."""
        return MockPlatformPrompt()


class MockPlatformParsers(PlatformParsers):
    """Mock parsers for testing."""

    def parse_text_content(self, content: str | bytes | dict) -> ResponseTextContent:
        """Mock parse text content."""
        if isinstance(content, dict):
            return ResponseTextContent(text=content.get("text", ""))
        return ResponseTextContent(text=str(content))

    def parse_image_content(self, content: str | bytes | dict) -> ResponseImageContent:
        """Mock parse image content."""
        return ResponseImageContent(
            mime_type="image/jpeg",
            value="mock_image_value",
        )

    def parse_audio_content(self, content: str | bytes | dict) -> ResponseAudioContent:
        """Mock parse audio content."""
        return ResponseAudioContent(
            mime_type="audio/wav",
            value="mock_audio_value",
        )

    def parse_tool_use_content(
        self,
        content: str | bytes | dict,
    ) -> ResponseToolUseContent:
        """Mock parse tool use content."""
        return ResponseToolUseContent(
            tool_call_id="mock_tool_call_id",
            tool_name="mock_tool_name",
            tool_input_raw=json.dumps({"input": "value"}),
        )

    def parse_document_content(
        self,
        content: str | bytes | dict,
    ) -> ResponseDocumentContent:
        """Mock parse document content."""
        return ResponseDocumentContent(
            mime_type="application/pdf",
            value="mock_document_value",
            name="mock_document_name",
        )

    def parse_content_item(self, item: str | bytes | dict) -> ResponseTextContent:
        """Mock parse content item."""
        return self.parse_text_content(item)

    def parse_response(self, response: str | bytes | dict) -> ResponseMessage:
        """Mock parse response."""
        return ResponseMessage(
            role="agent",
            content=[self.parse_text_content("mock response")],
        )


class MockPlatformConfigs(PlatformConfigs):
    """Mock platform configs for testing."""


class MockPlatformClient(PlatformClient):
    """Mock platform client for testing."""

    NAME: ClassVar[str] = "mock_platform"

    def _init_converters(
        self,
        kernel: Kernel | None = None,
    ) -> MockPlatformConverters:
        """Initialize mock converters."""
        converters = MockPlatformConverters()
        if kernel is not None:
            converters.attach_kernel(kernel)
        return converters

    def _init_parsers(self) -> MockPlatformParsers:
        """Initialize mock parsers."""
        return MockPlatformParsers()

    def _init_parameters(
        self,
        parameters: PlatformParameters | dict | None = None,
        **kwargs: Any,
    ) -> MockPlatformParameters:
        """Initialize mock parameters."""
        return MockPlatformParameters()

    def _init_configs(self) -> MockPlatformConfigs:
        """Initialize mock configs."""
        return MockPlatformConfigs()

    async def generate_response(
        self,
        prompt: PlatformPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a mock response."""
        return ResponseMessage(
            role="agent",
            content=[ResponseTextContent(text="mock response")],
        )

    async def generate_stream_response(
        self,
        prompt: PlatformPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Generate a mock stream response."""
        yield GenericDelta(
            op="add",
            path="",
            value="Hello",
        )
        yield GenericDelta(
            op="add",
            path="",
            value=", world!",
        )

    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Mock implementation of create_embeddings method.

        Args:
            texts: A list of texts to embed.
            model: The model to use for embedding.

        Returns:
            A dictionary with embeddings, usage, and model info.
        """
        # Generate mock embeddings of dimension 3
        mock_embeddings = [[0.1, 0.2, 0.3] for _ in texts]

        # Create a mock response similar to what the real method returns
        return {
            "embeddings": mock_embeddings,
            "model": model,
            "usage": {
                "prompt_tokens": sum(len(text.split()) for text in texts),
                "total_tokens": sum(len(text.split()) for text in texts),
            },
        }


# Tests for base platform components
class TestPlatformBaseComponents:
    """Tests for the platform base components."""

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def mock_platform_client(self, kernel: Kernel) -> MockPlatformClient:
        """Create a mock platform client for testing."""
        return MockPlatformClient(kernel=kernel)

    def test_platform_client_initialization(self, kernel: Kernel) -> None:
        """Test that the platform client initializes correctly."""
        client = MockPlatformClient(kernel=kernel)

        assert client.name == "mock_platform"
        assert isinstance(client.converters, MockPlatformConverters)
        assert isinstance(client.parsers, MockPlatformParsers)
        assert isinstance(client.parameters, MockPlatformParameters)
        assert isinstance(client.configs, MockPlatformConfigs)

    def test_platform_client_attach_kernel(
        self,
        mock_platform_client: MockPlatformClient,
    ) -> None:
        """Test that the platform client attaches a kernel correctly."""
        new_kernel = MagicMock(spec=Kernel)

        # Make the component's attach_kernel methods return mocks so we can verify calls
        mock_converters = MagicMock()

        # Save references to the original components
        original_converters = mock_platform_client.converters

        # Replace the attach_kernel methods with mocks
        with patch.object(
            original_converters,
            "attach_kernel",
            return_value=mock_converters,
        ):
            # Attach a new kernel
            mock_platform_client.attach_kernel(new_kernel)

            # Verify that attach_kernel was called on each component
            original_converters.attach_kernel.assert_called_with(  # type: ignore
                new_kernel,
            )

    @pytest.mark.asyncio
    async def test_platform_client_generate_response(
        self,
        mock_platform_client: MockPlatformClient,
    ) -> None:
        """Test that the platform client generates a response correctly."""
        prompt = MagicMock(spec=Prompt)

        response = await mock_platform_client.generate_response(prompt, "mock_model")

        assert isinstance(response, ResponseMessage)
        assert response.role == "agent"
        assert len(response.content) == 1
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "mock response"

    @pytest.mark.asyncio
    async def test_platform_client_generate_stream_response(
        self,
        mock_platform_client: MockPlatformClient,
    ) -> None:
        """Test that the platform client generates a stream response correctly."""
        prompt = MagicMock(spec=Prompt)

        responses = []
        async for response in mock_platform_client.generate_stream_response(
            prompt,
            model="mock_model",
        ):
            responses.append(response)

        assert len(responses) == 2
        assert isinstance(responses[0], GenericDelta)
        assert isinstance(responses[1], GenericDelta)
        assert responses[0].op == "add"
        assert responses[1].op == "add"
        assert responses[0].path == ""
        assert responses[1].path == ""
        assert responses[0].value == "Hello"
        assert responses[1].value == ", world!"

    def test_platform_client_generate_platform_metadata(
        self,
        mock_platform_client: MockPlatformClient,
    ) -> None:
        """Test that the platform client generates platform metadata correctly."""
        metadata = mock_platform_client._generate_platform_metadata()

        assert metadata == {
            "sema4ai_metadata": {
                "platform_name": "mock_platform",
            },
        }

    @pytest.mark.asyncio
    async def test_platform_converters_convert_content_item(
        self,
        mock_platform_client: MockPlatformClient,
    ) -> None:
        """Test that platform converters convert content items correctly."""
        converters = mock_platform_client.converters

        # Test text content
        text_content = PromptTextContent(text="Hello, World!")
        text_result = await converters.convert_content_item_to_platform_part(
            text_content,
        )
        assert text_result == {"type": "text", "text": "Hello, World!"}

        # Test unsupported content type
        invalid_content = MagicMock(spec=PromptMessageContent)
        invalid_content.kind = "unsupported"
        with pytest.raises(
            ValueError,
            match="Unsupported PromptMessageContent type: unsupported",
        ):
            await converters.convert_content_item_to_platform_part(invalid_content)
