"""Unit tests for the OpenAI platform client."""

from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Iterable,
    Iterator,
)
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.client import OpenAIClient
from agent_platform.core.platforms.openai.configs import OpenAIModelMap
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString


class MockStreamResponse(AsyncIterable, Iterable):
    """Mock response for streaming that can be both awaited and iterated."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.async_chunks = list(chunks)  # Create a copy for async iteration

    def __iter__(self) -> Iterator:
        yield from self.chunks

    def __aiter__(self) -> AsyncIterator:
        return self

    async def __anext__(self):
        if not self.async_chunks:
            raise StopAsyncIteration
        return self.async_chunks.pop(0)


async def mock_async_generator(
    items: list[GenericDelta],
) -> AsyncGenerator[GenericDelta, None]:
    """Helper function to create an async generator from a list of items."""
    for item in items:
        yield item


class MockCompletions:
    """Mock completions API."""

    def __init__(self):
        self.create = MagicMock()


class MockChatCompletions:
    """Mock chat completions API."""

    def __init__(self):
        self.completions = MockCompletions()


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        self.chat = MockChatCompletions()


class TestOpenAIClient:
    """Tests for the OpenAI client."""

    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create a mock OpenAI client."""
        client = MockOpenAIClient()

        # Set up chat completions response for non-streaming
        def mock_chat_response(**kwargs):
            if kwargs.get("stream", False):
                # Return a mock async iterable for streaming
                chunks = [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "role": "assistant",
                                },
                            },
                        ],
                    },
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": "Hello, ",
                                },
                            },
                        ],
                    },
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": "world!",
                                },
                            },
                        ],
                    },
                ]
                return MockStreamResponse(chunks)
            else:
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hello, world!",
                            },
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                }

        client.chat.completions.create.side_effect = mock_chat_response

        return client

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> OpenAIPlatformParameters:
        """Create OpenAI platform parameters for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            return OpenAIPlatformParameters(
                openai_api_key=mock_secret,
            )

    @pytest.fixture
    def openai_client(
        self,
        kernel: Kernel,
        parameters: OpenAIPlatformParameters,
        mock_openai_client: Any,
    ) -> OpenAIClient:
        """Create an OpenAI client for testing."""
        with patch("openai.OpenAI", return_value=mock_openai_client):
            client = OpenAIClient(
                kernel=kernel,
                parameters=parameters,
            )

            # Mock the response parser
            mock_response = ResponseMessage(
                content=[ResponseTextContent(text="Hello, world!")],
                raw_response={},
                role="agent",
            )
            client._parsers.parse_response = MagicMock(return_value=mock_response)

            # Mock the stream event parser to return an AsyncGenerator
            deltas = [
                GenericDelta(
                    op="add",
                    path="/content/0/text",
                    value="Hello, ",
                ),
                GenericDelta(
                    op="add",
                    path="/content/0/text",
                    value="world!",
                ),
            ]

            # Create a factory function that returns our mock async generator
            def mock_parse_stream(*args, **kwargs):
                return mock_async_generator(deltas)

            client._parsers.parse_stream_event = mock_parse_stream

            return client

    @pytest.fixture
    def prompt(self) -> Prompt:
        """Create a prompt for testing."""
        return Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage([PromptTextContent(text="Hello, world!")]),
            ],
        )

    @pytest.fixture
    def openai_prompt(self) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt()

    def test_init(self, parameters: OpenAIPlatformParameters) -> None:
        """Test client initialization."""
        with patch("openai.OpenAI") as mock_openai:
            client = OpenAIClient(parameters=parameters)
            assert client.name == "openai"
            assert isinstance(client._parameters, OpenAIPlatformParameters)
            assert client._parameters.openai_api_key is not None
            mock_openai.assert_called_once_with(
                api_key=client._parameters.openai_api_key.get_secret_value(),
            )

    def test_init_clients(self, parameters: OpenAIPlatformParameters) -> None:
        """Test client initialization with OpenAI client."""
        mock_client = MockOpenAIClient()
        with patch("openai.OpenAI", return_value=mock_client) as mock_openai:
            client = OpenAIClient(parameters=parameters)
            assert parameters.openai_api_key is not None
            mock_openai.assert_called_once_with(
                api_key=parameters.openai_api_key.get_secret_value(),
            )
            assert client._openai_client is mock_client

    def test_init_parameters_with_updates(
        self,
        parameters: OpenAIPlatformParameters,
    ) -> None:
        """Test parameter initialization with updates."""
        new_secret = SecretString("new-api-key")
        with (
            patch("openai.OpenAI"),
            patch("agent_platform.core.utils.SecretString", return_value=new_secret),
        ):
            updated_params = parameters.model_copy(
                update={"openai_api_key": new_secret},
            )
            client = OpenAIClient(parameters=updated_params)
            assert client._parameters.openai_api_key is not None
            assert client._parameters.openai_api_key.get_secret_value() == "new-api-key"

    @pytest.mark.asyncio
    @patch.object(
        OpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
        },
    )
    async def test_generate_response(
        self,
        mock_as_platform_request: MagicMock,
        openai_client: OpenAIClient,
        openai_prompt: OpenAIPrompt,
        mock_openai_client: Any,
    ) -> None:
        """Test generating a response."""
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": "gpt-4",
        }
        with patch.object(
            OpenAIModelMap,
            "__class_getitem__",
            return_value=test_model_map["gpt-4"],
        ):
            response = await openai_client.generate_response(
                prompt=openai_prompt,
                model="gpt-4",
            )

            mock_openai_client.chat.completions.create.assert_called_once()
            assert isinstance(response, ResponseMessage)
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    @patch.object(
        OpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
            "stream": True,
        },
    )
    async def test_generate_stream_response(
        self,
        mock_as_platform_request: MagicMock,
        openai_client: OpenAIClient,
        openai_prompt: OpenAIPrompt,
        mock_openai_client: Any,
    ) -> None:
        """Test generating a stream response."""
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": "gpt-4",
        }

        with patch.object(
            OpenAIModelMap,
            "__class_getitem__",
            return_value=test_model_map["gpt-4"],
        ):
            deltas = []
            async for delta in openai_client.generate_stream_response(
                prompt=openai_prompt,
                model="gpt-4",
            ):
                deltas.append(delta)

            mock_openai_client.chat.completions.create.assert_called_once()
            assert len(deltas) > 0
            assert all(isinstance(d, GenericDelta) for d in deltas)

    @pytest.mark.asyncio
    async def test_create_embeddings_not_implemented(
        self,
        openai_client: OpenAIClient,
    ) -> None:
        """Test that create_embeddings raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError,
            match="OpenAI embeddings are not yet implemented",
        ):
            await openai_client.create_embeddings(
                texts=["Hello, world!"],
                model="text-embedding-ada-002",
            )
