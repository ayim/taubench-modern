"""Unit tests for the AzureOpenAI platform client."""

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
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.azure.client import AzureOpenAIClient
from agent_platform.core.platforms.azure.parameters import (
    AzureOpenAIPlatformParameters,
)
from agent_platform.core.platforms.azure.prompts import AzureOpenAIPrompt
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


class MockResponses:
    """Mock Responses API."""

    def __init__(self):
        self.create = MagicMock()


class MockModels:
    """Mock models API."""

    def __init__(self):
        self.list = MagicMock()


class MockAzureOpenAIClient:
    """Mock AzureOpenAI client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        # Keep chat for backward compatibility (unused in aligned client)
        self.chat = MagicMock()
        self.responses = MockResponses()
        self.embeddings = MockEmbeddings()
        self.models = MockModels()


class TestAzureOpenAIClient:
    """Tests for the AzureOpenAI client."""

    @pytest.fixture
    def mock_azure_client(self) -> Any:
        """Create a mock AzureOpenAI client."""
        client = MockAzureOpenAIClient()

        # Set up Responses API response for non-streaming and streaming
        async def mock_responses_create(**kwargs):
            from types import SimpleNamespace

            # Simulate streaming by returning an async iterable of events
            if kwargs.get("stream", False):
                # Define minimal event types to satisfy parser logic
                def make_event(name: str, **fields):
                    return SimpleNamespace(type=name, **fields)

                # Build a sequence of events similar to OpenAI stream
                response_obj = SimpleNamespace(
                    id="resp_1",
                    model=kwargs.get("model", "gpt-5"),
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
                model=kwargs.get("model", "gpt-5"),
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
            embedding_size = 1536  # Common AzureOpenAI embedding size
            embedding = [0.1] * embedding_size
            token_count = len(text.split())

            return CreateEmbeddingResponse(
                object="list",
                data=[Embedding(embedding=embedding, index=0, object="embedding")],
                model=kwargs.get("model", "text-embedding-3-small"),
                usage=Usage(prompt_tokens=token_count, total_tokens=token_count),
            )

        client.embeddings.create.side_effect = mock_embedding_response

        return client

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> AzureOpenAIPlatformParameters:
        """Create AzureOpenAI platform parameters for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            return AzureOpenAIPlatformParameters(
                azure_api_key=mock_secret,
                azure_endpoint_url="https://test-endpoint.openai.azure.com",
                azure_deployment_name="gpt-5",
                azure_deployment_name_embeddings="text-embedding-3-small",
                azure_model_backing_deployment_name="gpt-5",
                azure_model_backing_deployment_name_embeddings="text-embedding-3-small",
                azure_api_version="2023-03-15-preview",
            )

    @pytest.fixture
    def azure_client(
        self,
        kernel: Kernel,
        parameters: AzureOpenAIPlatformParameters,
        mock_azure_client: Any,
    ) -> AzureOpenAIClient:
        """Create an AzureOpenAI client for testing."""
        with patch("openai.AsyncOpenAI", return_value=mock_azure_client):
            client = AzureOpenAIClient(
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

            # Mock the _init_embeddings_client method to return the same mock client
            # This ensures that the lazy loading also uses the mocked client
            client._init_embeddings_client = MagicMock(return_value=mock_azure_client)

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
    def azure_prompt(self) -> AzureOpenAIPrompt:
        """Create an AzureOpenAI prompt for testing."""
        return AzureOpenAIPrompt()

    def test_init(self, parameters: AzureOpenAIPlatformParameters) -> None:
        """Test client initialization."""
        with patch("openai.AsyncOpenAI") as mock_azure:
            client = AzureOpenAIClient(parameters=parameters)
            assert client.name == "azure"
            assert isinstance(client._parameters, AzureOpenAIPlatformParameters)
            assert client._parameters.azure_api_key is not None
            mock_azure.assert_called()

    def test_init_clients(self, parameters: AzureOpenAIPlatformParameters) -> None:
        """Test client initialization with AzureOpenAI client."""
        mock_client = MockAzureOpenAIClient()
        with patch("openai.AsyncOpenAI", return_value=mock_client) as mock_azure:
            client = AzureOpenAIClient(parameters=parameters)
            assert parameters.azure_api_key is not None
            # Client gets initialized once for completions (embeddings client is lazy)
            assert mock_azure.call_count == 1
            assert client._azure_client is mock_client
            # Embeddings client should be None until first access
            assert client._azure_embeddings_client is None

    def test_init_parameters_with_updates(
        self,
        parameters: AzureOpenAIPlatformParameters,
    ) -> None:
        """Test parameter initialization with updates."""
        new_secret = SecretString("new-api-key")
        with (
            patch("openai.AsyncAzureOpenAI"),
            patch("agent_platform.core.utils.SecretString", return_value=new_secret),
        ):
            updated_params = parameters.model_copy(
                update={"azure_api_key": new_secret},
            )
            client = AzureOpenAIClient(parameters=updated_params)
            assert client._parameters.azure_api_key is not None
            assert client._parameters.azure_api_key.get_secret_value() == "new-api-key"

    @pytest.mark.asyncio
    @patch.object(
        AzureOpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-5",
            "input": [
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
        },
    )
    async def test_generate_response(
        self,
        mock_as_platform_request: MagicMock,
        azure_client: AzureOpenAIClient,
        azure_prompt: AzureOpenAIPrompt,
        mock_azure_client: Any,
    ) -> None:
        """Test generating a response."""
        response = await azure_client.generate_response(
            prompt=azure_prompt,
            model="gpt-5-medium",
        )

        mock_azure_client.responses.create.assert_called_once()
        assert isinstance(response, ResponseMessage)
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    @patch.object(
        AzureOpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-5",
            "input": [
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )
    async def test_generate_stream_response(
        self,
        mock_as_platform_request: MagicMock,
        azure_client: AzureOpenAIClient,
        azure_prompt: AzureOpenAIPrompt,
        mock_azure_client: Any,
    ) -> None:
        """Test generating a stream response."""
        deltas = []
        async for delta in azure_client.generate_stream_response(
            prompt=azure_prompt,
            model="gpt-5-medium",
        ):
            deltas.append(delta)

        mock_azure_client.responses.create.assert_called_once()
        assert len(deltas) > 0
        assert all(isinstance(d, GenericDelta) for d in deltas)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        [
            "text-embedding-3-small",
        ],
    )
    async def test_create_embeddings_single_text(
        self,
        azure_client: AzureOpenAIClient,
        embedding_model: str,
        mock_azure_client: Any,
    ) -> None:
        """Test creating embeddings for a single text."""
        text = "This is a test text for embedding"
        result = await azure_client.create_embeddings([text], embedding_model)

        # Verify API call
        mock_azure_client.embeddings.create.assert_called_once_with(
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
        assert len(result["embeddings"][0]) == 1536  # Common AzureOpenAI embedding size
        assert result["model"] == embedding_model
        assert "total_tokens" in result["usage"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        [
            "text-embedding-3-small",
        ],
    )
    async def test_create_embeddings_batch(
        self,
        azure_client: AzureOpenAIClient,
        embedding_model: str,
        mock_azure_client: Any,
    ) -> None:
        """Test creating embeddings for multiple texts."""
        texts = ["First test text", "Second test text", "Third test text"]
        result = await azure_client.create_embeddings(texts, embedding_model)

        # Verify API calls (one per text)
        assert mock_azure_client.embeddings.create.call_count == len(texts)
        for i, text in enumerate(texts):
            call_args = mock_azure_client.embeddings.create.call_args_list[i][1]
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
        azure_client: AzureOpenAIClient,
        mock_azure_client: Any,
    ) -> None:
        """Test creating embeddings with empty text list."""
        embedding_model = "text-embedding-3-small"

        result = await azure_client.create_embeddings([], embedding_model)

        # Verify no API calls made
        mock_azure_client.embeddings.create.assert_not_called()

        # Verify result is empty but structured correctly
        assert isinstance(result, dict)
        assert "embeddings" in result
        assert len(result["embeddings"]) == 0
        assert "model" in result
        assert result["model"] == embedding_model
        assert "usage" in result
        assert "total_tokens" in result["usage"]
        assert result["usage"]["total_tokens"] == 0

    def test_handle_openai_apierror_rate_limit_stream(
        self,
        azure_client: AzureOpenAIClient,
    ) -> None:
        """Ensure APIError with rate limit code maps to TOO_MANY_REQUESTS."""
        import httpx
        from openai._exceptions import APIError

        request = httpx.Request("POST", "https://example.com")
        api_error = APIError(
            message="Rate limit is exceeded. Try again in 10 seconds.",
            request=request,
            body={"code": "rate_limit_exceeded"},
        )

        streaming_error = azure_client._handle_openai_error(
            api_error,
            model="azure/openai/gpt-4-1",
            error_type=StreamingError,
        )

        assert isinstance(streaming_error, StreamingError)
        assert streaming_error.response.error_code == ErrorCode.TOO_MANY_REQUESTS
