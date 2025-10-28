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

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
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


class MockGroqError(Exception):
    """Mock Groq error for testing."""

    def __init__(self, message: str = "Test error", body: dict | None = None):
        self.message = message
        self.body = body or {"error": {"message": message}}
        super().__init__(message)

    def __str__(self):
        return self.message


class TestGroqErrorHandling:
    """Tests for Groq client error handling functionality."""

    @pytest.fixture
    def groq_client(self) -> GroqClient:
        """Create a GroqClient instance for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            parameters = GroqPlatformParameters(groq_api_key=mock_secret)

        with patch("groq.AsyncGroq"):
            return GroqClient(parameters=parameters)

    def test_handle_groq_error_rate_limit_error(self, groq_client: GroqClient) -> None:
        """Test handling of RateLimitError."""
        with patch("groq.RateLimitError", MockGroqError):
            error = MockGroqError("Rate limit exceeded")
            error.__class__.__name__ = "RateLimitError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "too_many_requests"
            assert "usage limit reached" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_authentication_error(self, groq_client: GroqClient) -> None:
        """Test handling of AuthenticationError."""
        with patch("groq.AuthenticationError", MockGroqError):
            error = MockGroqError("Invalid API key")
            error.__class__.__name__ = "AuthenticationError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unauthorized"
            assert "authentication failed" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_permission_denied(self, groq_client: GroqClient) -> None:
        """Test handling of PermissionDeniedError."""
        with patch("groq.PermissionDeniedError", MockGroqError):
            error = MockGroqError("Access denied")
            error.__class__.__name__ = "PermissionDeniedError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "forbidden"
            assert "access denied" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_bad_request(self, groq_client: GroqClient) -> None:
        """Test handling of BadRequestError."""
        with patch("groq.BadRequestError", MockGroqError):
            error = MockGroqError("Invalid request")
            error.__class__.__name__ = "BadRequestError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "bad_request"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_not_found(self, groq_client: GroqClient) -> None:
        """Test handling of NotFoundError."""
        with patch("groq.NotFoundError", MockGroqError):
            error = MockGroqError("Model not found")
            error.__class__.__name__ = "NotFoundError"

            result = groq_client._handle_groq_error(error, "invalid-model")

            assert isinstance(result, PlatformError)
            assert result.response.code == "not_found"
            assert "not found" in result.response.message.lower()
            assert result.data["model"] == "invalid-model"

    def test_handle_groq_error_unprocessable_entity(self, groq_client: GroqClient) -> None:
        """Test handling of UnprocessableEntityError."""
        with patch("groq.UnprocessableEntityError", MockGroqError):
            error = MockGroqError("Request validation failed")
            error.__class__.__name__ = "UnprocessableEntityError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unprocessable_entity"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_conflict(self, groq_client: GroqClient) -> None:
        """Test handling of ConflictError."""
        with patch("groq.ConflictError", MockGroqError):
            error = MockGroqError("Request conflict")
            error.__class__.__name__ = "ConflictError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "conflict"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_timeout(self, groq_client: GroqClient) -> None:
        """Test handling of APITimeoutError."""
        with patch("groq.APITimeoutError", MockGroqError):
            error = MockGroqError("Request timed out")
            error.__class__.__name__ = "APITimeoutError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "timed out" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_connection_error(self, groq_client: GroqClient) -> None:
        """Test handling of APIConnectionError."""
        with patch("groq.APIConnectionError", MockGroqError):
            error = MockGroqError("Connection failed")
            error.__class__.__name__ = "APIConnectionError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "failed to connect" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_internal_server_error(self, groq_client: GroqClient) -> None:
        """Test handling of InternalServerError."""
        with patch("groq.InternalServerError", MockGroqError):
            error = MockGroqError("Internal server error")
            error.__class__.__name__ = "InternalServerError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "internal error" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_api_error_base_class(self, groq_client: GroqClient) -> None:
        """Test handling of base APIError class."""
        with patch("groq.APIError", MockGroqError):
            error = MockGroqError("Generic API error")
            error.__class__.__name__ = "APIError"

            result = groq_client._handle_groq_error(error, "llama-3.3")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "unexpected error" in result.response.message.lower()
            assert result.data["model"] == "llama-3.3"

    def test_handle_groq_error_unknown_exception(self, groq_client: GroqClient) -> None:
        """Test handling of unknown exceptions (should re-raise)."""
        error = ValueError("Some unexpected error")

        with pytest.raises(ValueError, match="Some unexpected error"):
            groq_client._handle_groq_error(error, "llama-3.3")

    def test_handle_groq_error_with_custom_error_type(self, groq_client: GroqClient) -> None:
        """Test that custom error types are respected."""
        with patch("groq.RateLimitError", MockGroqError):
            error = MockGroqError("Rate limit exceeded")
            error.__class__.__name__ = "RateLimitError"

            result = groq_client._handle_groq_error(error, "llama-3.3", PlatformHTTPError)

            assert isinstance(result, PlatformHTTPError)
            assert result.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, groq_client: GroqClient) -> None:
        """Test error handling in generate_response method."""
        groq_prompt = GroqPrompt()

        # Mock the Groq client to raise an exception
        with patch("groq.RateLimitError", MockGroqError):
            error = MockGroqError("Rate limit exceeded")
            error.__class__.__name__ = "RateLimitError"

            with patch.object(groq_client, "_client") as mock_client:
                mock_client.chat.completions.create.side_effect = error

                with pytest.raises(PlatformHTTPError) as exc_info:
                    await groq_client.generate_response(groq_prompt, "llama-3.3")

                assert exc_info.value.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_stream_response_error_handling(self, groq_client: GroqClient) -> None:
        """Test error handling in generate_stream_response method."""
        groq_prompt = GroqPrompt()

        # Mock the Groq client to raise an exception
        with patch("groq.PermissionDeniedError", MockGroqError):
            error = MockGroqError("Access denied")
            error.__class__.__name__ = "PermissionDeniedError"

            with patch.object(groq_client, "_client") as mock_client:
                mock_client.chat.completions.create.side_effect = error

                with pytest.raises(StreamingError) as exc_info:
                    async for _ in groq_client.generate_stream_response(groq_prompt, "llama-3.3"):
                        pass  # This shouldn't execute due to the exception

                assert exc_info.value.response.code == "forbidden"

    @pytest.mark.asyncio
    async def test_create_embeddings_error_handling(self, groq_client: GroqClient) -> None:
        """Test error handling in create_embeddings method."""
        # Mock the Groq client to raise an exception
        with patch("groq.BadRequestError", MockGroqError):
            error = MockGroqError("Invalid model parameters")
            error.__class__.__name__ = "BadRequestError"

            # Mock embeddings method
            mock_embeddings = MagicMock()
            mock_embeddings.create.side_effect = error

            with patch.object(groq_client, "_client") as mock_client:
                mock_client.embeddings = mock_embeddings

                with pytest.raises(PlatformHTTPError) as exc_info:
                    await groq_client.create_embeddings(["test text"], "llama-3.3")

                assert exc_info.value.response.code == "bad_request"


class TestGroqClient:
    """Tests for the Groq client."""

    @pytest.fixture
    def mock_groq_client(self) -> Any:
        """Create a mock Groq client."""
        client = MockGroqClient()

        # Set up chat completions response for non-streaming
        async def mock_chat_response(**kwargs):
            from groq.types.chat import ChatCompletion
            from groq.types.chat.chat_completion import Choice
            from groq.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
            from groq.types.chat.chat_completion_chunk import Choice as ChunkChoice
            from groq.types.chat.chat_completion_message import ChatCompletionMessage
            from groq.types.completion_usage import CompletionUsage

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
