"""Unit tests for the Google platform client."""

import json
import os
from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Iterable,
    Iterator,
)
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import status

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.platforms.google.client import GoogleClient
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


class MockGoogleGenAIError(Exception):
    """Mock Google GenAI error for testing."""

    def __init__(self, code: int, message: str, status: str | None = None):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"{self.code} {self.status}. {self.message}")

    def __str__(self):
        return f"{self.code} {self.status}. {self.message}"


class TestGoogleErrorHandling:
    """Tests for Google client error handling functionality."""

    @pytest.fixture
    def google_client(self) -> GoogleClient:
        """Create a GoogleClient instance for testing."""
        mock_secret = SecretString("test-api-key")
        with patch("agent_platform.core.utils.SecretString", return_value=mock_secret):
            parameters = GooglePlatformParameters(google_api_key=mock_secret)

        with patch("google.genai.Client"):
            return GoogleClient(parameters=parameters)

    def test_handle_google_error_bad_request(self, google_client: GoogleClient) -> None:
        """Test handling of 400 Bad Request error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_400_BAD_REQUEST,
                message="Invalid request parameters",
                status="INVALID_ARGUMENT",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "bad_request"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_400_BAD_REQUEST
            assert result.data["status"] == "INVALID_ARGUMENT"

    def test_handle_google_error_unauthorized(self, google_client: GoogleClient) -> None:
        """Test handling of 401 Unauthorized error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid API key",
                status="UNAUTHENTICATED",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unauthorized"
            assert "authentication failed" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_401_UNAUTHORIZED

    def test_handle_google_error_forbidden(self, google_client: GoogleClient) -> None:
        """Test handling of 403 Forbidden error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_403_FORBIDDEN,
                message="Access denied to model",
                status="PERMISSION_DENIED",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "forbidden"
            assert "access denied" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_403_FORBIDDEN

    def test_handle_google_error_not_found(self, google_client: GoogleClient) -> None:
        """Test handling of 404 Not Found error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_404_NOT_FOUND,
                message="Model not found",
                status="NOT_FOUND",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "invalid-model")

            assert isinstance(result, PlatformError)
            assert result.response.code == "not_found"
            assert "not found" in result.response.message.lower()
            assert result.data["model"] == "invalid-model"
            assert result.data["status_code"] == status.HTTP_404_NOT_FOUND

    def test_handle_google_error_unprocessable_entity(self, google_client: GoogleClient) -> None:
        """Test handling of 422 Unprocessable Entity error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Request validation failed",
                status="INVALID_ARGUMENT",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unprocessable_entity"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_handle_google_error_too_many_requests(self, google_client: GoogleClient) -> None:
        """Test handling of 429 Too Many Requests error."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                message="Rate limit exceeded",
                status="RESOURCE_EXHAUSTED",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "too_many_requests"
            assert "usage limit reached" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_429_TOO_MANY_REQUESTS

    def test_handle_google_error_other_client_error(self, google_client: GoogleClient) -> None:
        """Test handling of other 4xx client errors."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=418,  # I'm a teapot
                message="I'm a teapot",
                status="UNAVAILABLE",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "bad_request"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["status_code"] == 418

    def test_handle_google_error_internal_server_error(self, google_client: GoogleClient) -> None:
        """Test handling of 500 Internal Server Error."""
        with patch("google.genai.errors.ServerError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Internal server error",
                status="INTERNAL",
            )
            error.__class__.__name__ = "ServerError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["model"] == "gemini-3-pro-preview"
            assert result.data["status_code"] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_handle_google_error_service_unavailable(self, google_client: GoogleClient) -> None:
        """Test handling of 503 Service Unavailable error."""
        with patch("google.genai.errors.ServerError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                message="Service temporarily unavailable",
                status="UNAVAILABLE",
            )
            error.__class__.__name__ = "ServerError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "currently unavailable" in result.response.message.lower()
            assert result.data["status_code"] == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_handle_google_error_unknown_status_code(self, google_client: GoogleClient) -> None:
        """Test handling of unknown status codes."""
        with patch("google.genai.errors.APIError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=999,  # Unknown status code
                message="Unknown error",
                status="UNKNOWN",
            )
            error.__class__.__name__ = "APIError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "unexpected"
            assert "something went wrong" in result.response.message.lower()
            assert result.data["status_code"] == 999

    def test_handle_google_error_api_error_base_class(self, google_client: GoogleClient) -> None:
        """Test handling of base APIError class."""
        with patch("google.genai.errors.APIError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_400_BAD_REQUEST,
                message="Generic API error",
                status="INVALID_ARGUMENT",
            )
            error.__class__.__name__ = "APIError"

            result = google_client._handle_google_error(error, "gemini-3-pro-preview")

            assert isinstance(result, PlatformError)
            assert result.response.code == "bad_request"
            assert "something went wrong" in result.response.message.lower()

    def test_handle_google_error_unknown_exception(self, google_client: GoogleClient) -> None:
        """Test handling of unknown exceptions (should re-raise)."""
        error = ValueError("Some unexpected error")

        with pytest.raises(ValueError, match="Some unexpected error"):
            google_client._handle_google_error(error, "gemini-3-pro-preview")

    def test_handle_google_error_with_custom_error_type(self, google_client: GoogleClient) -> None:
        """Test that custom error types are respected."""
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                message="Rate limit exceeded",
                status="RESOURCE_EXHAUSTED",
            )
            error.__class__.__name__ = "ClientError"

            result = google_client._handle_google_error(
                error,
                "gemini-3-pro-preview",
                PlatformHTTPError,
            )

            assert isinstance(result, PlatformHTTPError)
            assert result.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, google_client: GoogleClient) -> None:
        """Test error handling in generate_response method."""
        google_prompt = GooglePrompt()

        # Mock the Google GenAI client to raise an exception
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                message="Rate limit exceeded",
                status="RESOURCE_EXHAUSTED",
            )
            error.__class__.__name__ = "ClientError"

            with patch.object(google_client, "_google_client") as mock_client:
                mock_client.aio.models.generate_content.side_effect = error

                with patch(
                    "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
                    new=AsyncMock(return_value="gemini-2.5-pro"),
                ):
                    with pytest.raises(PlatformHTTPError) as exc_info:
                        await google_client.generate_response(google_prompt, "gemini-2.5-pro")

                assert exc_info.value.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_stream_response_error_handling(self, google_client: GoogleClient) -> None:
        """Test error handling in generate_stream_response method."""
        google_prompt = GooglePrompt()

        # Mock the Google GenAI client to raise an exception
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_403_FORBIDDEN,
                message="Access denied",
                status="PERMISSION_DENIED",
            )
            error.__class__.__name__ = "ClientError"

            with patch.object(google_client, "_google_client") as mock_client:
                mock_client.aio.models.generate_content_stream.side_effect = error

                with patch(
                    "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
                    new=AsyncMock(return_value="gemini-3-pro-preview"),
                ):
                    with pytest.raises(StreamingError) as exc_info:
                        async for _ in google_client.generate_stream_response(google_prompt, "gemini-3-pro-preview"):
                            pass  # This shouldn't execute due to the exception

                assert exc_info.value.response.code == "forbidden"

    @pytest.mark.asyncio
    async def test_create_embeddings_error_handling(self, google_client: GoogleClient) -> None:
        """Test error handling in create_embeddings method."""
        # Mock the Google GenAI client to raise an exception
        with patch("google.genai.errors.ClientError", MockGoogleGenAIError):
            error = MockGoogleGenAIError(
                code=status.HTTP_400_BAD_REQUEST,
                message="Invalid model parameters",
                status="INVALID_ARGUMENT",
            )
            error.__class__.__name__ = "ClientError"

            with patch.object(google_client, "_google_client") as mock_client:
                mock_client.aio.models.embed_content.side_effect = error

                with pytest.raises(PlatformHTTPError) as exc_info:
                    await google_client.create_embeddings(["test text"], "google/google/text-embedding-004")

                assert exc_info.value.response.code == "bad_request"


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
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_USE_VERTEX_AI": "",
                    "GOOGLE_VERTEX_SERVICE_ACCOUNT_JSON": "",
                    "GOOGLE_CLOUD_PROJECT_ID": "",
                    "GOOGLE_CLOUD_LOCATION": "",
                },
                clear=False,
            ),
            patch("agent_platform.core.utils.SecretString", return_value=mock_secret),
        ):
            return GooglePlatformParameters(
                google_api_key=mock_secret,
                google_use_vertex_ai=False,
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

        contents = cast(list[Content], [content1, content2])

        return GooglePrompt(
            contents=contents,
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=4096,
        )

    def test_init(self, parameters: GooglePlatformParameters) -> None:
        """Test client initialization."""
        from google.genai.types import HttpOptions

        with patch("google.genai.Client") as mock_client:
            client = GoogleClient(parameters=parameters)
            assert client.name == "google"
            assert isinstance(client._parameters, GooglePlatformParameters)
            assert client._parameters.google_api_key is not None

            # Verify call without relying on object identity for the transport
            mock_client.assert_called_once()
            called_kwargs = mock_client.call_args.kwargs
            assert called_kwargs["api_key"] == client._parameters.google_api_key.get_secret_value()
            http_options = called_kwargs["http_options"]
            assert isinstance(http_options, HttpOptions)
            assert http_options.async_client_args is not None
            assert isinstance(
                http_options.async_client_args.get("transport"),
                httpx.AsyncHTTPTransport,
            )
            assert "vertexai" not in called_kwargs or not called_kwargs["vertexai"]

    def test_build_vertex_credentials_returns_none_when_not_vertex(
        self,
        parameters: GooglePlatformParameters,
    ) -> None:
        with patch("google.genai.Client"):
            client = GoogleClient(parameters=parameters)
        assert client._build_vertex_credentials() is None

    def test_update_token_counters_from_chunk_tracks_max(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Token counters should use the max values observed from the stream."""
        chunk = MagicMock()
        usage_metadata = MagicMock()
        usage_metadata.prompt_token_count = 20
        usage_metadata.candidates_token_count = 10
        usage_metadata.total_token_count = None
        usage_metadata.thoughts_token_count = 5
        chunk.usage_metadata = usage_metadata

        counters = {"prompt": 5, "completion": 7, "total": 12, "thinking": 2}

        google_client._update_token_counters_from_chunk(chunk, counters)

        assert counters["prompt"] == 20
        assert counters["completion"] == 10
        assert counters["total"] == 30
        assert counters["thinking"] == 5

    def test_update_token_counters_ignores_chunks_without_usage(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Chunks that omit metadata should not mutate counters."""
        chunk = MagicMock()
        chunk.usage_metadata = None
        counters = {"prompt": 1, "completion": 2, "total": 3, "thinking": 4}

        google_client._update_token_counters_from_chunk(chunk, counters)

        assert counters == {"prompt": 1, "completion": 2, "total": 3, "thinking": 4}

    def test_add_final_metadata_sets_usage_and_token_metrics(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Final metadata should include platform info, usage, and thinking tokens."""
        message: dict[str, Any] = {}
        counters = {"prompt": 11, "completion": 13, "total": 24, "thinking": 3}

        google_client._add_final_metadata(message, counters)

        assert message["usage"] == {
            "input_tokens": 11,
            "output_tokens": 13,
            "total_tokens": 24,
        }
        token_metrics = message["metadata"]["token_metrics"]
        assert token_metrics["thinking_tokens"] == 3
        assert message["metadata"]["sema4ai_metadata"]["platform_name"] == "google"

    def test_normalize_google_models_adds_provider_specific_ids(self) -> None:
        """Allow list entries should be deduped and augmented with provider IDs."""
        params = GooglePlatformParameters(
            google_api_key=SecretString("test-api-key"),
            google_use_vertex_ai=False,
            models={
                "google": [
                    "google/google/gemini-3-pro-high",
                    "gemini-3-pro-preview",
                ],
            },
        )

        with patch("google.genai.Client"):
            client = GoogleClient(parameters=params)

        normalized = client._normalize_google_models(
            client._get_configured_google_models(),
        )

        assert normalized.count("gemini-3-pro-preview") == 1
        assert "google/google/gemini-3-pro-high" in normalized
        # Alias and provider IDs should both be present once
        assert len(normalized) == 2

    def test_load_service_account_info_from_json_string(
        self,
        parameters: GooglePlatformParameters,
    ) -> None:
        """Service account JSON strings should be parsed without hitting disk."""
        with patch("google.genai.Client"):
            client = GoogleClient(parameters=parameters)

        info = client._load_service_account_info(json.dumps({"type": "service_account"}))
        assert info is not None
        assert info["type"] == "service_account"

    def test_load_service_account_info_from_file_path(
        self,
        parameters: GooglePlatformParameters,
        tmp_path,
    ) -> None:
        """Service account helper should read from filesystem paths."""
        sa_path = tmp_path / "account.json"
        sa_path.write_text(json.dumps({"client_email": "foo@example.com"}), encoding="utf-8")

        with patch("google.genai.Client"):
            client = GoogleClient(parameters=parameters)

        info = client._load_service_account_info(str(sa_path))
        assert info is not None
        assert info["client_email"] == "foo@example.com"

    def test_load_service_account_info_invalid_content_raises(
        self,
        parameters: GooglePlatformParameters,
    ) -> None:
        """Invalid service account values should raise a ValueError."""
        with patch("google.genai.Client"):
            client = GoogleClient(parameters=parameters)

        with pytest.raises(
            ValueError,
            match="Invalid service account JSON provided for Vertex AI authentication",
        ):
            client._load_service_account_info("not-a-json-or-path")

    def test_build_vertex_credentials_uses_service_account_json(self) -> None:
        """Vertex credential helper should hydrate google auth credentials."""
        service_account_data = {
            "type": "service_account",
            "project_id": "demo",
            "private_key": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----\n",
            "client_email": "demo@example.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        service_account_json = SecretString(json.dumps(service_account_data))

        with (
            patch("google.genai.Client"),
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_info",
                return_value=MagicMock(name="credentials"),
            ) as mock_creds,
        ):
            params = GooglePlatformParameters(
                google_use_vertex_ai=True,
                google_cloud_project_id="project-123",
                google_cloud_location="us-central1",
                google_vertex_service_account_json=service_account_json,
            )
            client = GoogleClient(parameters=params)

            creds = client._build_vertex_credentials()

        assert creds is mock_creds.return_value
        assert mock_creds.call_count >= 1

    def test_init_vertex_ai_without_credentials_raises_error(self) -> None:
        """Vertex AI configuration without credentials should fail at runtime."""
        api_key = SecretString("test-api-key")
        with patch.dict(os.environ, {}, clear=True):
            params = GooglePlatformParameters(
                google_api_key=api_key,
                google_use_vertex_ai=True,
                google_cloud_project_id="project-123",
                google_cloud_location="us-central1",
            )

            with (
                patch("google.genai.Client"),
                pytest.raises(ValueError, match="google_vertex_service_account_json"),
            ):
                GoogleClient(parameters=params)

    def test_init_vertex_ai_without_api_key_succeeds_with_service_account(self) -> None:
        """Vertex AI initialization does not require API key when service account is provided."""
        service_account_data = {
            "type": "service_account",
            "project_id": "demo",
            "private_key": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----\n",
            "client_email": "demo@example.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        service_account_json = SecretString(json.dumps(service_account_data))
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("google.genai.Client"),
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_info",
                return_value=MagicMock(name="credentials"),
            ),
        ):
            params = GooglePlatformParameters(
                google_use_vertex_ai=True,
                google_cloud_project_id="project-123",
                google_cloud_location="us-central1",
                google_vertex_service_account_json=service_account_json,
            )
            GoogleClient(parameters=params)

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

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value="gemini-2.5-pro"),
        ):
            response = await google_client.generate_response(
                prompt=google_prompt,
                model="gemini-2.5-pro",
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

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value="gemini-2.5-pro"),
        ):
            deltas = []
            async for delta in google_client.generate_stream_response(
                prompt=google_prompt,
                model="gemini-2.5-pro",
            ):
                deltas.append(delta)

            # Verify deltas were produced
            assert len(deltas) > 0
            assert all(isinstance(d, GenericDelta) for d in deltas)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "embedding_model",
        ["google/google/text-embedding-004"],
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

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value=embedding_model),
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
        ["google/google/text-embedding-004"],
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

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value=embedding_model),
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
        embedding_model = "google/google/text-embedding-004"

        # Create flags to track if functions were called
        embed_content_called = False

        async def mock_embed_content(*args, **kwargs):
            nonlocal embed_content_called
            embed_content_called = True
            return MagicMock()

        google_client._google_client.aio.models.embed_content = mock_embed_content

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value=embedding_model),
        ):
            result = await google_client.create_embeddings([], embedding_model)

            # Verify no API calls made (no errors)
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

        with patch(
            "agent_platform.core.platforms.google.client.resolve_generic_model_id_to_platform_specific_model_id",
            new=AsyncMock(return_value="gemini-2.5-pro"),
        ):
            response = await google_client.generate_response(
                prompt=google_prompt,
                model="gemini-2.5-pro",
            )

            # Verify token usage
            assert response.usage.input_tokens == 100
            assert response.usage.output_tokens == 50
            assert response.usage.total_tokens == 150
            assert "token_metrics" in response.metadata
            assert "thinking_tokens" in response.metadata["token_metrics"]
            assert response.metadata["token_metrics"]["thinking_tokens"] == 25

    @pytest.mark.asyncio
    async def test_get_available_models_returns_configured_values(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Ensure model availability is sourced solely from configs."""
        with patch.object(
            GoogleClient,
            "_get_configured_google_models",
            return_value=["gemini-3-pro-preview", "gemini-2.5-pro"],
        ) as mock_config_models:
            google_client._available_models_cache.clear()
            available = await google_client.get_available_models()

        mock_config_models.assert_called_once()
        assert available == {
            "google": ["gemini-3-pro-preview", "gemini-2.5-pro"],
        }

    @pytest.mark.asyncio
    async def test_get_available_models_uses_cache(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Ensure results are cached after first resolution."""
        with patch.object(
            GoogleClient,
            "_get_configured_google_models",
            return_value=["gemini-3-pro-preview"],
        ) as mock_config_models:
            google_client._available_models_cache.clear()
            await google_client.get_available_models()
            await google_client.get_available_models()

        mock_config_models.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_generic_model_id_accepts_generic_allowlist(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Generic aliases in allow-list should still resolve to provider IDs."""
        google_client.get_available_models = AsyncMock(  # type: ignore[assignment]
            return_value={"google": ["gemini-3-pro-preview"]},
        )

        resolved = await resolve_generic_model_id_to_platform_specific_model_id(
            google_client,
            "google/google/gemini-3-pro-low",
        )

        assert resolved == "gemini-3-pro-preview"

    @pytest.mark.asyncio
    async def test_resolve_generic_model_id_accepts_fully_qualified_alias(
        self,
        google_client: GoogleClient,
    ) -> None:
        """Fully qualified aliases should also resolve correctly."""
        google_client.get_available_models = AsyncMock(  # type: ignore[assignment]
            return_value={"google": ["gemini-3-pro-preview"]},
        )

        resolved = await resolve_generic_model_id_to_platform_specific_model_id(
            google_client,
            "google/google/gemini-3-pro-low",
        )

        assert resolved == "gemini-3-pro-preview"
