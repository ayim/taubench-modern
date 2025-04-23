"""Unit tests for the Groq platform client."""

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
from groq.types.chat import ChatCompletion
from groq.types.chat.chat_completion import Choice
from groq.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
from groq.types.chat.chat_completion_chunk import Choice as ChunkChoice
from groq.types.chat.chat_completion_message import ChatCompletionMessage
from groq.types.completion_usage import CompletionUsage

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.groq.client import GroqClient
from agent_platform.core.platforms.groq.configs import GroqModelMap
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.platforms.groq.prompts import GroqPrompt
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


class MockGroqClient:
    """Mock Groq client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        self.chat = MockChatCompletions()


class TestGroqClient:
    """Tests for the Groq client."""

    @pytest.fixture
    def mock_groq_client(self) -> Any:
        """Create a mock Groq client."""
        client = MockGroqClient()

        # Set up chat completions response for non-streaming
        async def mock_chat_response(**kwargs):
            if kwargs.get("stream", False):
                chunks = [
                    ChatCompletionChunk(
                        id="chunk1",
                        object="chat.completion.chunk",
                        created=1,
                        model="llama-3.3",
                        x_groq=None,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=ChoiceDelta(
                                    role="assistant",
                                    content="Hello, ",
                                ),
                                finish_reason=None,
                            )
                        ],
                    ),
                    ChatCompletionChunk(
                        id="chunk2",
                        object="chat.completion.chunk",
                        created=2,
                        model="llama-3.3",
                        x_groq=None,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=ChoiceDelta(
                                    role="assistant",
                                    content="world!",
                                ),
                                finish_reason=None,
                            )
                        ],
                    ),
                ]
                return MockStreamResponse(chunks)
            else:
                return ChatCompletion(
                    id="resp1",
                    object="chat.completion",
                    created=1,
                    model="llama-3.3",
                    choices=[
                        Choice(
                            index=0,
                            message=ChatCompletionMessage(
                                role="assistant",
                                content="Hello, world!",
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=CompletionUsage(
                        prompt_tokens=10,
                        completion_tokens=20,
                        total_tokens=30,
                    ),
                )

        client.chat.completions.create.side_effect = mock_chat_response

        return client

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> GroqPlatformParameters:
        """Create Groq platform parameters for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            return GroqPlatformParameters(
                groq_api_key=mock_secret,
            )

    @pytest.fixture
    def groq_client(
        self,
        kernel: Kernel,
        parameters: GroqPlatformParameters,
        mock_groq_client: Any,
    ) -> GroqClient:
        """Create a Groq client for testing."""
        with patch("groq.AsyncGroq", return_value=mock_groq_client):
            client = GroqClient(
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
    def groq_prompt(self) -> GroqPrompt:
        """Create a Groq prompt for testing."""
        return GroqPrompt()

    def test_init(self, parameters: GroqPlatformParameters) -> None:
        """Test client initialization."""
        with patch("groq.AsyncGroq") as mock_groq:
            client = GroqClient(parameters=parameters)
            assert client.name == "groq"
            assert isinstance(client._parameters, GroqPlatformParameters)
            assert client._parameters.groq_api_key is not None
            mock_groq.assert_called_once_with(
                api_key=client._parameters.groq_api_key.get_secret_value(),
            )

    @pytest.mark.asyncio
    @patch.object(
        GroqPrompt,
        "as_platform_request",
        return_value={
            "model": "llama-3.3",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
        },
    )
    async def test_generate_response(
        self,
        mock_as_platform_request: MagicMock,
        groq_client: GroqClient,
        groq_prompt: GroqPrompt,
        mock_groq_client: Any,
    ) -> None:
        """Test generating a response."""
        test_model_map = {"llama-3.3": "llama-3.3"}
        with patch.object(GroqModelMap, "model_aliases", test_model_map):
            response = await groq_client.generate_response(
                prompt=groq_prompt,
                model="llama-3.3",
            )

            mock_groq_client.chat.completions.create.assert_called_once()
            assert isinstance(response, ResponseMessage)
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    @patch.object(
        GroqPrompt,
        "as_platform_request",
        return_value={
            "model": "llama-3.3",
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
        groq_client: GroqClient,
        groq_prompt: GroqPrompt,
        mock_groq_client: Any,
    ) -> None:
        """Test generating a stream response."""
        test_model_map = {"llama-3.3": "llama-3.3"}

        with patch.object(GroqModelMap, "model_aliases", test_model_map):
            deltas = []
            async for delta in groq_client.generate_stream_response(
                prompt=groq_prompt,
                model="llama-3.3",
            ):
                deltas.append(delta)

            mock_groq_client.chat.completions.create.assert_called_once()
            assert len(deltas) > 2, "Should have at least two deltas"
            assert all(isinstance(d, GenericDelta) for d in deltas)
            assert any(
                d.op == "add" and d.path == "/content/0/text" and d.value == "Hello, "
                for d in deltas
            )
            assert any(
                d.op == "add" and d.path == "/content/0/text" and d.value == "world!"
                for d in deltas
            )
