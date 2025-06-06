"""Unit tests for the Google platform client."""

from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Iterable,
    Iterator,
)
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai.types import Content, Part

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.google.client import GoogleClient
from agent_platform.core.platforms.google.configs import GoogleModelMap
from agent_platform.core.platforms.google.parameters import GooglePlatformParameters
from agent_platform.core.platforms.google.prompts import GooglePrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage
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


class MockGenerateContentResponse:
    """Mock generate content response."""

    def __init__(self, text="Hello, world!", usage_metadata=None):
        self.candidates = [self._create_candidate(text)]
        self.usage_metadata = usage_metadata or self._create_usage_metadata()

    def _create_candidate(self, text):
        content = MagicMock()
        part = MagicMock()
        part.text = text
        part.function_call = None
        content.parts = [part]

        candidate = MagicMock()
        candidate.content = content
        candidate.finish_reason = "STOP"
        return candidate

    def _create_usage_metadata(self):
        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 10
        usage_metadata.candidates_token_count = 20
        usage_metadata.total_token_count = 30
        usage_metadata.thoughts_token_count = 5
        return usage_metadata

    def __await__(self):
        async def _awaitable():
            return self

        return _awaitable().__await__()


class TestGoogleClient:
    """Tests for the Google client."""

    @pytest.fixture
    def mock_google_genai(self) -> Any:
        """Create a mock for Google's generative AI library."""
        mock_genai = MagicMock()
        return mock_genai

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> GooglePlatformParameters:
        """Create Google platform parameters for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            return GooglePlatformParameters(
                google_api_key=mock_secret,
            )

    @pytest.fixture
    def google_client(
        self,
        kernel: Kernel,
        parameters: GooglePlatformParameters,
        mock_google_genai: Any,
    ) -> GoogleClient:
        """Create a Google client for testing."""
        # Create client side mocks
        mock_aio = MagicMock()
        mock_models = MagicMock()

        # Create awaitable mock methods with proper typing
        async_generate = AsyncMock(return_value=MockGenerateContentResponse())
        mock_models.generate_content = async_generate

        async_stream = AsyncMock(
            return_value=MockStreamResponse([MagicMock(), MagicMock()]),
        )
        mock_models.generate_content_stream = async_stream

        async_count = AsyncMock()

        async def mock_count_tokens(**kwargs):
            result = MagicMock()
            result.total_tokens = 50
            return result

        async_count.side_effect = mock_count_tokens
        mock_models.count_tokens = async_count

        async_embed = AsyncMock()

        async def mock_embed_content(**kwargs):
            result = MagicMock()
            result.embedding = MagicMock()
            result.embedding.values = [0.1] * 768
            return result

        async_embed.side_effect = mock_embed_content
        mock_models.embed_content = async_embed

        # Set up the mock structure
        mock_aio.models = mock_models
        mock_google_genai.aio = mock_aio

        # Patch the Google GenAI Client
        with patch("google.genai.Client", return_value=mock_google_genai):
            client = GoogleClient(
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
    def google_prompt(self) -> GooglePrompt:
        """Create a Google prompt for testing."""
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

        contents = cast(list[Content], [content1, content2])

        return GooglePrompt(
            contents=contents,
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=4096,
        )

    def test_init(self, parameters: GooglePlatformParameters) -> None:
        """Test client initialization."""
        with patch("google.genai.Client") as mock_client:
            client = GoogleClient(parameters=parameters)
            assert client.name == "google"
            assert isinstance(client._parameters, GooglePlatformParameters)
            assert client._parameters.google_api_key is not None
            mock_client.assert_called_once_with(
                api_key=client._parameters.google_api_key.get_secret_value(),
            )

    def test_init_parameters_with_updates(
        self,
        parameters: GooglePlatformParameters,
    ) -> None:
        """Test parameter initialization with updates."""
        new_secret = SecretString("new-api-key")
        with (
            patch("google.genai.Client"),
            patch(
                "agent_platform.core.utils.SecretString",
                return_value=new_secret,
            ),
        ):
            updated_params = parameters.model_copy(
                update={"google_api_key": new_secret},
            )
            client = GoogleClient(parameters=updated_params)
            assert client._parameters.google_api_key is not None
            assert client._parameters.google_api_key.get_secret_value() == "new-api-key"

    @pytest.mark.asyncio
    async def test_generate_response(
        self,
        google_client: GoogleClient,
        google_prompt: GooglePrompt,
    ) -> None:
        """Test generating a response."""
        # Create a response with custom usage metadata
        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 10
        usage_metadata.candidates_token_count = 20
        usage_metadata.total_token_count = 30
        usage_metadata.thoughts_token_count = 5

        mock_response = MockGenerateContentResponse(
            usage_metadata=usage_metadata,
        )

        # Set up the mock to return our custom response
        async_mock = AsyncMock(return_value=mock_response)
        google_client._google_client.aio.models.generate_content = async_mock

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value="gemini-1.5-pro",
        ):
            response = await google_client.generate_response(
                prompt=google_prompt,
                model="gemini-1.5-pro",
            )

            # Check response structure without asserting on the parser
            assert async_mock.called
            assert isinstance(response, ResponseMessage)
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_generate_stream_response(
        self,
        google_client: GoogleClient,
        google_prompt: GooglePrompt,
    ) -> None:
        """Test generating a stream response."""
        # Create a mock for the streaming response
        mock_chunks = [MagicMock(), MagicMock()]
        mock_stream = MockStreamResponse(mock_chunks)

        # Set up the mock to return our custom response
        async_mock = AsyncMock(return_value=mock_stream)
        google_client._google_client.aio.models.generate_content_stream = async_mock

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value="gemini-1.5-pro",
        ):
            deltas = []
            async for delta in google_client.generate_stream_response(
                prompt=google_prompt,
                model="gemini-1.5-pro",
            ):
                deltas.append(delta)

            # Verify deltas were produced
            assert len(deltas) > 0
            assert all(isinstance(d, GenericDelta) for d in deltas)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        ["gemini-embedding-exp-03-07", "models/text-embedding-004"],
    )
    async def test_create_embeddings_single_text(
        self,
        google_client: GoogleClient,
        embedding_model: str,
    ) -> None:
        """Test creating embeddings for a single text."""
        # Mock embedding function with the new structure
        mock_embedding = MagicMock()
        mock_embedding_values = MagicMock()
        mock_embedding_values.values = [0.1] * 768
        mock_embedding.embeddings = [mock_embedding_values]

        # Create async function with proper typing
        async_mock = AsyncMock(return_value=mock_embedding)
        google_client._google_client.aio.models.embed_content = async_mock

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value=embedding_model,
        ):
            text = "This is a test text for embedding"
            result = await google_client.create_embeddings([text], embedding_model)

            # Verify the client calls were made
            assert async_mock.called, "embed_content was not called"

            # Verify result structure
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert "model" in result
            assert "usage" in result

            # Verify embedding data
            assert len(result["embeddings"]) == 1
            assert len(result["embeddings"][0]) == 768
            assert result["model"] == embedding_model
            assert "total_tokens" in result["usage"]
            assert result["usage"]["total_tokens"] == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        ["gemini-embedding-exp-03-07", "models/text-embedding-004"],
    )
    async def test_create_embeddings_batch(
        self,
        google_client: GoogleClient,
        embedding_model: str,
    ) -> None:
        """Test creating embeddings for multiple texts."""
        # Mock embedding function with the new structure
        mock_embedding = MagicMock()
        mock_embedding_values = MagicMock()
        mock_embedding_values.values = [0.1] * 768
        mock_embedding.embeddings = [mock_embedding_values]

        # Create async function with proper typing
        async_mock = AsyncMock(return_value=mock_embedding)
        google_client._google_client.aio.models.embed_content = async_mock

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value=embedding_model,
        ):
            texts = ["First test text", "Second test text", "Third test text"]
            result = await google_client.create_embeddings(texts, embedding_model)

            # Verify the client calls were made the correct number of times
            # (once per text)
            assert async_mock.call_count == len(
                texts,
            ), f"embed_content was called {async_mock.call_count} times,"
            f"expected {len(texts)}"

            # Verify result structure
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == len(texts)
            assert "model" in result
            assert result["model"] == embedding_model
            assert "usage" in result
            assert "total_tokens" in result["usage"]
            # We no longer count tokens for embeddings, so this should be 0
            assert result["usage"]["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_create_embeddings_empty_texts(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Test creating embeddings with empty text list."""
        embedding_model = "models/text-embedding-004"

        # Create flags to track if functions were called
        count_tokens_called = False
        embed_content_called = False

        async def mock_count_tokens(*args, **kwargs):
            nonlocal count_tokens_called
            count_tokens_called = True
            return MagicMock()

        async def mock_embed_content(*args, **kwargs):
            nonlocal embed_content_called
            embed_content_called = True
            return MagicMock()

        google_client._google_client.aio.models.count_tokens = mock_count_tokens
        google_client._google_client.aio.models.embed_content = mock_embed_content

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value=embedding_model,
        ):
            result = await google_client.create_embeddings([], embedding_model)

            # Verify no API calls made (no errors)
            assert not count_tokens_called, "count_tokens should not be called"
            assert not embed_content_called, "embed_content should not be called"

            # Verify result structure
            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == 0
            assert "model" in result
            assert result["model"] == embedding_model
            assert "usage" in result
            assert "total_tokens" in result["usage"]
            assert result["usage"]["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_token_usage_reporting(
        self,
        google_client: GoogleClient,
        google_prompt: GooglePrompt,
    ) -> None:
        """Test that token usage is properly reported in the response."""
        # Create a response with usage metadata
        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 100
        usage_metadata.candidates_token_count = 50
        usage_metadata.total_token_count = 150
        usage_metadata.thoughts_token_count = 25

        mock_response = MockGenerateContentResponse(
            usage_metadata=usage_metadata,
        )

        # Create expected TokenUsage
        expected_token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        # Create expected response with correct token usage
        expected_response = ResponseMessage(
            content=[ResponseTextContent(text="Hello, world!")],
            role="agent",
            usage=expected_token_usage,
            metadata={"token_metrics": {"thinking_tokens": 25}},
        )

        # Set up mocks to return our response
        async_mock = AsyncMock(return_value=mock_response)
        google_client._google_client.aio.models.generate_content = async_mock
        google_client._parsers.parse_response = MagicMock()
        google_client._parsers.parse_response.return_value = expected_response

        with patch.object(
            GoogleModelMap,
            "model_aliases",
            return_value="gemini-1.5-pro",
        ):
            response = await google_client.generate_response(
                prompt=google_prompt,
                model="gemini-1.5-pro",
            )

            # Verify token usage
            assert response.usage.input_tokens == 100
            assert response.usage.output_tokens == 50
            assert response.usage.total_tokens == 150
            assert "token_metrics" in response.metadata
            assert "thinking_tokens" in response.metadata["token_metrics"]
            assert response.metadata["token_metrics"]["thinking_tokens"] == 25
