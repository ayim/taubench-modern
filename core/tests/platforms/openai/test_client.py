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


class MockEmbeddingData:
    """Mock embedding data response."""

    def __init__(self, embedding: list[float]):
        self.embedding = embedding


class MockEmbeddingResponse:
    """Mock response for embedding API."""

    def __init__(self, embedding: list[float], tokens: int):
        self.data = [MockEmbeddingData(embedding)]
        self.usage = MagicMock()
        self.usage.total_tokens = tokens


class MockEmbeddings:
    """Mock embeddings API."""

    def __init__(self):
        self.create = MagicMock()


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
        self.embeddings = MockEmbeddings()


class TestOpenAIClient:
    """Tests for the OpenAI client."""

    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create a mock OpenAI client."""
        client = MockOpenAIClient()

        # Set up chat completions response for non-streaming
        async def mock_chat_response(**kwargs):
            from openai.types.chat import ChatCompletion
            from openai.types.chat.chat_completion import Choice
            from openai.types.chat.chat_completion_message import ChatCompletionMessage
            from openai.types.completion_usage import CompletionUsage

            if kwargs.get("stream", False):
                # Return a mock async iterable for streaming
                from openai.types.chat.chat_completion_chunk import (
                    ChatCompletionChunk,
                    ChoiceDelta,
                )
                from openai.types.chat.chat_completion_chunk import (
                    Choice as ChunkChoice,
                )

                chunks = [
                    ChatCompletionChunk(
                        id="chunk1",
                        object="chat.completion.chunk",
                        created=1234567890,
                        model=kwargs.get("model", "default-model"),
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=ChoiceDelta(role="assistant"),
                                finish_reason=None,
                            ),
                        ],
                    ),
                    ChatCompletionChunk(
                        id="chunk2",
                        object="chat.completion.chunk",
                        created=1234567891,
                        model=kwargs.get("model", "default-model"),
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=ChoiceDelta(content="Hello, "),
                                finish_reason=None,
                            ),
                        ],
                    ),
                    ChatCompletionChunk(
                        id="chunk3",
                        object="chat.completion.chunk",
                        created=1234567892,
                        model=kwargs.get("model", "default-model"),
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=ChoiceDelta(content="world!"),
                                finish_reason="stop",
                            ),
                        ],
                    ),
                ]
                return MockStreamResponse(chunks)
            else:
                return ChatCompletion(
                    id="response-id",
                    object="chat.completion",
                    created=1234567890,
                    model=kwargs.get("model", "default-model"),
                    choices=[
                        Choice(
                            index=0,
                            message=ChatCompletionMessage(
                                role="assistant",
                                content="Hello, world!",
                            ),
                            finish_reason="stop",
                        ),
                    ],
                    usage=CompletionUsage(
                        prompt_tokens=10,
                        completion_tokens=20,
                        total_tokens=30,
                    ),
                )

        client.chat.completions.create.side_effect = mock_chat_response

        # Set up embeddings response
        async def mock_embedding_response(**kwargs):
            from openai.types.create_embedding_response import (
                CreateEmbeddingResponse,
                Usage,
            )
            from openai.types.embedding import Embedding

            text = kwargs.get("input", "")
            # Simple deterministic embedding based on text length
            embedding_size = 1536  # Common OpenAI embedding size
            embedding = [0.1] * embedding_size
            token_count = len(text.split())

            return CreateEmbeddingResponse(
                object="list",
                data=[Embedding(embedding=embedding, index=0, object="embedding")],
                model=kwargs.get("model", "text-embedding-ada-002"),
                usage=Usage(prompt_tokens=token_count, total_tokens=token_count),
            )

        client.embeddings.create.side_effect = mock_embedding_response

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
        with patch("openai.AsyncOpenAI", return_value=mock_openai_client):
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
        with patch("openai.AsyncOpenAI") as mock_openai:
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
        with patch("openai.AsyncOpenAI", return_value=mock_client) as mock_openai:
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
            patch("openai.AsyncOpenAI"),
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
            "model_aliases",
            test_model_map,
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
            "model_aliases",
            test_model_map,
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
    @pytest.mark.parametrize(
        "embedding_model",
        [
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
        ],
    )
    async def test_create_embeddings_single_text(
        self,
        openai_client: OpenAIClient,
        embedding_model: str,
        mock_openai_client: Any,
    ) -> None:
        """Test creating embeddings for a single text."""
        # Set up model map
        test_model_map = {
            "text-embedding-ada-002": "text-embedding-ada-002",
            "text-embedding-3-small": "text-embedding-3-small",
            "text-embedding-3-large": "text-embedding-3-large",
        }

        with patch.object(
            OpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            text = "This is a test text for embedding"
            result = await openai_client.create_embeddings([text], embedding_model)

            # Verify API call
            mock_openai_client.embeddings.create.assert_called_once_with(
                model=test_model_map[embedding_model],
                input=text,
            )

            # Verify result structure
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert "model" in result
            assert "usage" in result

            # Verify embedding data
            assert len(result["embeddings"]) == 1
            assert len(result["embeddings"][0]) == 1536  # Common OpenAI embedding size
            assert result["model"] == embedding_model
            assert "total_tokens" in result["usage"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        [
            "text-embedding-ada-002",
            "text-embedding-3-small",
        ],
    )
    async def test_create_embeddings_batch(
        self,
        openai_client: OpenAIClient,
        embedding_model: str,
        mock_openai_client: Any,
    ) -> None:
        """Test creating embeddings for multiple texts."""
        # Set up model map
        test_model_map = {
            "text-embedding-ada-002": "text-embedding-ada-002",
            "text-embedding-3-small": "text-embedding-3-small",
        }

        with patch.object(
            OpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            texts = ["First test text", "Second test text", "Third test text"]
            result = await openai_client.create_embeddings(texts, embedding_model)

            # Verify API calls (one per text)
            assert mock_openai_client.embeddings.create.call_count == len(texts)
            for i, text in enumerate(texts):
                call_args = mock_openai_client.embeddings.create.call_args_list[i][1]
                assert call_args["model"] == test_model_map[embedding_model]
                assert call_args["input"] == text

            # Verify result structure
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == len(texts)
            assert "model" in result
            assert result["model"] == embedding_model
            assert "usage" in result
            assert "total_tokens" in result["usage"]

    @pytest.mark.asyncio
    async def test_create_embeddings_empty_texts(
        self,
        openai_client: OpenAIClient,
        mock_openai_client: Any,
    ) -> None:
        """Test creating embeddings with empty text list."""
        embedding_model = "text-embedding-3-small"
        test_model_map = {
            "text-embedding-3-small": "text-embedding-3-small",
        }

        with patch.object(
            OpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            result = await openai_client.create_embeddings([], embedding_model)

            # Verify no API calls made
            mock_openai_client.embeddings.create.assert_not_called()

            # Verify result is empty but structured correctly
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == 0
            assert "model" in result
            assert result["model"] == embedding_model
            assert "usage" in result
            assert "total_tokens" in result["usage"]
            assert result["usage"]["total_tokens"] == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("prompt_data", "expected_tokens"),
        [
            # Test basic message
            (
                {
                    "messages": [
                        {"role": "user", "content": "Hello, world!"},
                    ],
                },
                6,  # "user: Hello, world!" should be 6 tokens
            ),
            # Test system and user messages
            (
                {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Hello, world!"},
                    ],
                },
                14,  # "system: You are a helpful assistant." + "user: Hello, world!"
            ),
            # Test with tools
            (
                {
                    "messages": [
                        {"role": "user", "content": "What's the weather?"},
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "description": "Get the current weather",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "location": {
                                            "type": "string",
                                            "description": (
                                                "The city to get weather for",
                                            ),
                                        },
                                    },
                                    "required": ["location"],
                                },
                            },
                        },
                    ],
                },
                59,  # Approximate token count for the message + tool definition
            ),
        ],
    )
    async def test_count_tokens(
        self,
        openai_client: OpenAIClient,
        prompt_data: dict[str, Any],
        expected_tokens: int,
    ) -> None:
        """Test counting tokens in different types of prompts.

        Args:
            openai_client: The OpenAI client to test.
            prompt_data: The prompt data to test with.
            expected_tokens: The expected number of tokens.
        """
        # Create a mock prompt that returns our test data
        mock_prompt = MagicMock(spec=OpenAIPrompt)
        mock_prompt.as_platform_request.return_value = prompt_data

        # Add the model to the model maps
        test_model_map = {
            "gpt-4o": "gpt-4o-2024-08-06",
        }
        with patch.object(
            OpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            token_count = await openai_client.count_tokens(
                prompt=mock_prompt,
                model="gpt-4o",
            )
            assert token_count == expected_tokens

    @pytest.mark.asyncio
    async def test_count_tokens_with_empty_prompt(
        self,
        openai_client: OpenAIClient,
    ) -> None:
        """Test counting tokens with an empty prompt."""
        mock_prompt = MagicMock(spec=OpenAIPrompt)
        mock_prompt.as_platform_request.return_value = {"messages": []}

        test_model_map = {
            "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
        }
        with patch.object(
            OpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            token_count = await openai_client.count_tokens(
                prompt=mock_prompt,
                model="gpt-3.5-turbo",
            )
            assert token_count == 0

    @pytest.mark.asyncio
    async def test_count_tokens_with_invalid_model(
        self,
        openai_client: OpenAIClient,
    ) -> None:
        """Test counting tokens with an invalid model."""
        mock_prompt = MagicMock(spec=OpenAIPrompt)
        mock_prompt.as_platform_request.return_value = {
            "messages": [{"role": "user", "content": "Hello"}],
        }

        with pytest.raises(KeyError):
            await openai_client.count_tokens(
                prompt=mock_prompt,
                model="invalid-model",
            )
