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


class MockResponses:
    """Mock Responses API."""

    def __init__(self):
        self.create = MagicMock()


class MockModels:
    """Mock models API."""

    def __init__(self):
        self.list = MagicMock()


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        self.responses = MockResponses()
        self.embeddings = MockEmbeddings()
        self.models = MockModels()


class TestOpenAIClient:
    """Tests for the OpenAI client."""

    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create a mock OpenAI client."""
        client = MockOpenAIClient()

        # Set up Responses API response for non-streaming and streaming
        async def mock_responses_create(**kwargs):
            from types import SimpleNamespace

            # Simulate streaming by returning an async iterable of events
            if kwargs.get("stream", False):
                from types import SimpleNamespace

                # Define minimal event types to satisfy parser logic
                def make_event(name: str, **fields):
                    return SimpleNamespace(type=name, **fields)

                # Build a sequence of events similar to OpenAI stream
                response_obj = SimpleNamespace(
                    id="resp_1",
                    model=kwargs.get("model", "default-model"),
                    usage=SimpleNamespace(input_tokens=10, output_tokens=20, total_tokens=30),
                )
                events = [
                    # Output message scaffold
                    make_event(
                        "response.output_item.added",
                        item=SimpleNamespace(
                            __class__=type("ResponseOutputMessage", (), {}),
                            id="msg_1",
                        ),
                    ),
                    # Text deltas
                    make_event("response.output_text.delta", delta="Hello, "),
                    make_event("response.output_text.delta", delta="world!"),
                    # Completed event with usage
                    make_event("response.completed", response=response_obj),
                ]
                return MockStreamResponse(events)

            # Non-streaming: return an object with .output and .usage
            output_message = SimpleNamespace(
                __class__=type("ResponseOutputMessage", (), {}),
                id="msg_1",
                content=[
                    SimpleNamespace(
                        __class__=type("ResponseOutputText", (), {}),
                        type="output_text",
                        text="Hello, world!",
                        annotations=[],
                        logprobs=None,
                    ),
                ],
            )
            response = SimpleNamespace(
                id="resp_1",
                model=kwargs.get("model", "default-model"),
                output=[output_message],
                usage=SimpleNamespace(input_tokens=10, output_tokens=20, total_tokens=30),
            )
            return response

        client.responses.create.side_effect = mock_responses_create

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
                model=kwargs.get("model", "text-embedding-3-small"),
                usage=Usage(prompt_tokens=token_count, total_tokens=token_count),
            )

        client.embeddings.create.side_effect = mock_embedding_response

        async def mock_models_list_response(**kwargs):
            from openai.types.model import Model

            return MagicMock(
                data=[
                    Model(
                        id="gpt-5-2025-08-07",
                        object="model",
                        created=1234567890,
                        owned_by="openai",
                    ),
                    Model(
                        id="gpt-4.1-2025-04-14",
                        object="model",
                        created=1234567890,
                        owned_by="openai",
                    ),
                    Model(
                        id="text-embedding-3-small",
                        object="model",
                        created=1234567890,
                        owned_by="openai",
                    ),
                    Model(
                        id="text-embedding-3-large",
                        object="model",
                        created=1234567890,
                        owned_by="openai",
                    ),
                ]
            )

        client.models.list.side_effect = mock_models_list_response

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
            assert (
                mock_openai.call_args.kwargs["api_key"]
                == client._parameters.openai_api_key.get_secret_value()
            )

    def test_init_clients(self, parameters: OpenAIPlatformParameters) -> None:
        """Test client initialization with OpenAI client."""
        mock_client = MockOpenAIClient()
        with patch("openai.AsyncOpenAI", return_value=mock_client) as mock_openai:
            client = OpenAIClient(parameters=parameters)
            assert parameters.openai_api_key is not None
            assert (
                mock_openai.call_args.kwargs["api_key"]
                == parameters.openai_api_key.get_secret_value()
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
            "model": "gpt-5",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ],
            "instructions": "You are a helpful assistant.",
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
        response = await openai_client.generate_response(
            prompt=openai_prompt,
            model="gpt-5-medium",
        )

        mock_openai_client.responses.create.assert_called_once()
        assert isinstance(response, ResponseMessage)
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    @patch.object(
        OpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-5",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello, world!"}],
                }
            ],
            "instructions": "You are a helpful assistant.",
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
        deltas = []
        async for delta in openai_client.generate_stream_response(
            prompt=openai_prompt,
            model="gpt-5-medium",
        ):
            deltas.append(delta)

        mock_openai_client.responses.create.assert_called_once()
        assert len(deltas) > 0
        assert all(isinstance(d, GenericDelta) for d in deltas)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        [
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
        text = "This is a test text for embedding"
        result = await openai_client.create_embeddings([text], embedding_model)

        # Verify API call
        mock_openai_client.embeddings.create.assert_called_once_with(
            model=embedding_model,
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
            "text-embedding-3-large",
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
        texts = ["First test text", "Second test text", "Third test text"]
        result = await openai_client.create_embeddings(texts, embedding_model)

        # Verify API calls (one per text)
        assert mock_openai_client.embeddings.create.call_count == len(texts)
        for i, text in enumerate(texts):
            call_args = mock_openai_client.embeddings.create.call_args_list[i][1]
            assert call_args["model"] == embedding_model
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
