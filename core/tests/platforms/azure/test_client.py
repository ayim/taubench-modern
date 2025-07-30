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
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.azure.client import AzureOpenAIClient
from agent_platform.core.platforms.azure.configs import AzureOpenAIModelMap
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


class MockCompletions:
    """Mock completions API."""

    def __init__(self):
        self.create = MagicMock()


class MockChatCompletions:
    """Mock chat completions API."""

    def __init__(self):
        self.completions = MockCompletions()


class MockAzureOpenAIClient:
    """Mock AzureOpenAI client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        self.chat = MockChatCompletions()
        self.embeddings = MockEmbeddings()


class TestAzureOpenAIClient:
    """Tests for the AzureOpenAI client."""

    @pytest.fixture
    def mock_azure_client(self) -> Any:
        """Create a mock AzureOpenAI client."""
        client = MockAzureOpenAIClient()

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
                    ChatCompletionChunk(
                        id="chunk4",
                        object="chat.completion.chunk",
                        created=1234567893,
                        model=kwargs.get("model", "default-model"),
                        choices=[],
                        usage=CompletionUsage(
                            prompt_tokens=10,
                            completion_tokens=20,
                            total_tokens=30,
                        ),
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
            embedding_size = 1536  # Common AzureOpenAI embedding size
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
    def parameters(self) -> AzureOpenAIPlatformParameters:
        """Create AzureOpenAI platform parameters for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            return AzureOpenAIPlatformParameters(
                azure_api_key=mock_secret,
                azure_endpoint_url="https://test-endpoint.openai.azure.com",
                azure_deployment_name="test-deployment",
                azure_deployment_name_embeddings="test-deployment-embeddings",
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
        with patch("openai.AsyncAzureOpenAI", return_value=mock_azure_client):
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
        with patch("openai.AsyncAzureOpenAI") as mock_azure:
            client = AzureOpenAIClient(parameters=parameters)
            assert client.name == "azure"
            assert isinstance(client._parameters, AzureOpenAIPlatformParameters)
            assert client._parameters.azure_api_key is not None
            mock_azure.assert_called()

    def test_init_clients(self, parameters: AzureOpenAIPlatformParameters) -> None:
        """Test client initialization with AzureOpenAI client."""
        mock_client = MockAzureOpenAIClient()
        with patch("openai.AsyncAzureOpenAI", return_value=mock_client) as mock_azure:
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
        azure_client: AzureOpenAIClient,
        azure_prompt: AzureOpenAIPrompt,
        mock_azure_client: Any,
    ) -> None:
        """Test generating a response."""
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": "gpt-4",
        }

        # Create a model map instance with our test mapping
        with patch.object(
            AzureOpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            response = await azure_client.generate_response(
                prompt=azure_prompt,
                model="gpt-4",
            )

            mock_azure_client.chat.completions.create.assert_called_once()
            assert isinstance(response, ResponseMessage)
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    @patch.object(
        AzureOpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
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
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": "gpt-4",
        }

        with patch.object(
            AzureOpenAIModelMap,
            "model_aliases",
            test_model_map,
        ):
            deltas = []
            async for delta in azure_client.generate_stream_response(
                prompt=azure_prompt,
                model="gpt-4",
            ):
                deltas.append(delta)

            mock_azure_client.chat.completions.create.assert_called_once()
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
        azure_client: AzureOpenAIClient,
        embedding_model: str,
        mock_azure_client: Any,
    ) -> None:
        """Test creating embeddings for a single text."""
        # Expected model mappings from AzureOpenAIModelMap
        expected_model_mappings = {
            "text-embedding-ada-002": "embedding-ada",
            "text-embedding-3-small": "embedding-3-small",
            "text-embedding-3-large": "embedding-3-large",
        }

        text = "This is a test text for embedding"
        result = await azure_client.create_embeddings([text], embedding_model)

        # Verify API call
        mock_azure_client.embeddings.create.assert_called_once_with(
            model=expected_model_mappings[embedding_model],
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
            "text-embedding-ada-002",
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
        # Expected model mappings from AzureOpenAIModelMap
        expected_model_mappings = {
            "text-embedding-ada-002": "embedding-ada",
            "text-embedding-3-small": "embedding-3-small",
        }

        texts = ["First test text", "Second test text", "Third test text"]
        result = await azure_client.create_embeddings(texts, embedding_model)

        # Verify API calls (one per text)
        assert mock_azure_client.embeddings.create.call_count == len(texts)
        for i, text in enumerate(texts):
            call_args = mock_azure_client.embeddings.create.call_args_list[i][1]
            assert call_args["model"] == expected_model_mappings[embedding_model]
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
