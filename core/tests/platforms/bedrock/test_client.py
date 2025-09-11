import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)
from botocore.exceptions import (
    ConnectionError as BotocoreConnectionError,
)

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.client import BedrockClient
from agent_platform.core.platforms.bedrock.configs import BedrockModelMap
from agent_platform.core.platforms.bedrock.converters import BedrockConverters
from agent_platform.core.platforms.bedrock.parameters import BedrockPlatformParameters
from agent_platform.core.platforms.bedrock.parsers import BedrockParsers
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage


class MockBedrockRuntimeClient:
    """Mock AWS Bedrock Runtime client for testing."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "system": "",
            "messages": [
                {"role": "user", "content": [{"text": "test message"}]},
                {"role": "assistant", "content": [{"text": "test response"}]},
            ],
        }

    def converse_stream(self, **kwargs: Any) -> dict[str, Any]:
        class MockStream:
            def __iter__(self):
                events = [
                    {
                        "chunk": {
                            "bytes": json.dumps(
                                {"delta": {"role": "assistant"}},
                            ).encode(),
                        },
                    },
                    {
                        "chunk": {
                            "bytes": json.dumps({"delta": {"content": []}}).encode(),
                        },
                    },
                    {
                        "chunk": {
                            "bytes": json.dumps(
                                {
                                    "delta": {
                                        "content": [{"type": "text", "text": "test"}],
                                    },
                                },
                            ).encode(),
                        },
                    },
                    {
                        "chunk": {
                            "bytes": json.dumps(
                                {
                                    "delta": {
                                        "content": [
                                            {"type": "text", "text": " response"},
                                        ],
                                    },
                                },
                            ).encode(),
                        },
                    },
                ]
                yield from events

        return {
            "stream": MockStream(),
            "ResponseMetadata": {
                "RequestId": "test-request-id",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Thu, 27 Feb 2025 18:52:25 GMT",
                    "content-type": "application/vnd.amazon.eventstream",
                    "transfer-encoding": "chunked",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "test-request-id",
                },
                "RetryAttempts": 0,
            },
        }


class TestBedrockErrorHandling:
    """Tests for Bedrock client error handling functionality."""

    @pytest.fixture
    def bedrock_client(self) -> BedrockClient:
        """Create a BedrockClient instance for testing."""
        parameters = BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )
        with patch("boto3.client"):
            client = BedrockClient(parameters=parameters)

            async def _mock_get_available_models() -> dict[str, list[str]]:
                return {
                    "amazon": [
                        "amazon.titan-embed-text-v2:0:8k",
                        "amazon.titan-embed-text-v1:2:8k",
                    ],
                    "cohere": [
                        "cohere.embed-english-v3:0:512",
                        "cohere.embed-multilingual-v3:0:512",
                    ],
                    "anthropic": [
                        "anthropic.claude-sonnet-4-20250514-v1:0",
                        "anthropic.claude-opus-4-20250514-v1:0",
                        "anthropic.claude-3-7-sonnet-20250219-v1:0",
                        "anthropic.claude-3-5-sonnet-20241022-v2:0",
                        "anthropic.claude-3-haiku-20240307-v1:0",
                    ],
                }

            client.get_available_models = _mock_get_available_models
            return client

    def test_handle_bedrock_error_throttling_exception(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ThrottlingException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Request rate exceeded",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "too_many_requests"
        assert "rate limit exceeded" in result.response.message
        assert result.data["model"] == "claude-3-sonnet"
        assert result.data["error_code"] == "ThrottlingException"
        assert result.data["technical_error_message"] == "Request rate exceeded"

    def test_handle_bedrock_error_access_denied(self, bedrock_client: BedrockClient) -> None:
        """Test handling of AccessDeniedException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied to model",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "forbidden"
        assert "Access denied" in result.response.message
        assert result.data["model"] == "claude-3-sonnet"
        assert result.data["region"] == "us-west-2"

    def test_handle_bedrock_error_validation_exception(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ValidationException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid input parameters",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "bad_request"
        assert "something went wrong" in result.response.message.lower()
        assert result.data["error_code"] == "ValidationException"

    def test_handle_bedrock_error_resource_not_found(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ResourceNotFoundException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Model not found",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "invalid-model")

        assert isinstance(result, PlatformError)
        assert result.response.code == "not_found"
        assert "not found" in result.response.message
        assert result.data["model"] == "invalid-model"

    def test_handle_bedrock_error_service_quota_exceeded(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of ServiceQuotaExceededException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ServiceQuotaExceededException",
                    "Message": "Service quota exceeded",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "too_many_requests"
        assert "quota exceeded" in result.response.message
        assert result.data["error_code"] == "ServiceQuotaExceededException"

    def test_handle_bedrock_error_model_timeout(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ModelTimeoutException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ModelTimeoutException",
                    "Message": "Model request timed out",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "timed out" in result.response.message
        assert result.data["error_code"] == "ModelTimeoutException"

    def test_handle_bedrock_error_internal_server_error(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of InternalServerException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "InternalServerException",
                    "Message": "Internal server error",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "internal error" in result.response.message
        assert result.data["error_code"] == "InternalServerException"

    def test_handle_bedrock_error_service_unavailable(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ServiceUnavailableException."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ServiceUnavailableException",
                    "Message": "Service temporarily unavailable",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "temporarily unavailable" in result.response.message

    def test_handle_bedrock_error_unknown_client_error(self, bedrock_client: BedrockClient) -> None:
        """Test handling of unknown ClientError codes."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "UnknownException",
                    "Message": "Unknown error occurred",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(client_error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "something went wrong" in result.response.message.lower()
        assert result.data["error_code"] == "UnknownException"

    def test_handle_bedrock_error_no_credentials(self, bedrock_client: BedrockClient) -> None:
        """Test handling of NoCredentialsError."""
        error = NoCredentialsError()

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unauthorized"
        assert "credentials" in result.response.message.lower()

    def test_handle_bedrock_error_connection_error(self, bedrock_client: BedrockClient) -> None:
        """Test handling of EndpointConnectionError."""
        error = EndpointConnectionError(endpoint_url="https://bedrock.us-west-2.amazonaws.com")

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "connect" in result.response.message.lower()

    def test_handle_bedrock_error_read_timeout(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ReadTimeoutError."""
        error = ReadTimeoutError(endpoint_url="https://bedrock.us-west-2.amazonaws.com")

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "timed out" in result.response.message

    def test_handle_bedrock_error_botocore_connection_error(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of botocore ConnectionError."""
        error = BotocoreConnectionError(error=Exception("Connection failed"))

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "network connection" in result.response.message.lower()

    def test_handle_bedrock_error_generic_botocore_error(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of generic BotoCoreError."""
        error = BotoCoreError()

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "something went wrong" in result.response.message.lower()

    def test_handle_bedrock_error_unknown_exception(self, bedrock_client: BedrockClient) -> None:
        """Test handling of unknown exceptions (should re-raise)."""
        error = ValueError("Some unexpected error")

        with pytest.raises(ValueError, match="Some unexpected error"):
            bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

    def test_handle_bedrock_error_with_custom_error_type(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test that custom error types are respected."""
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Rate limit exceeded",
                },
            },
            operation_name="converse",
        )

        result = bedrock_client._handle_bedrock_error(
            client_error, "claude-3-sonnet", PlatformHTTPError
        )

        assert isinstance(result, PlatformHTTPError)
        assert result.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, bedrock_client: BedrockClient) -> None:
        """Test error handling in generate_response method."""
        bedrock_prompt = BedrockPrompt()

        # Mock the boto3 client to raise an exception
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "Rate limit exceeded",
                },
            },
            operation_name="converse",
        )

        # Use a real model from the existing model map
        # Speed up test: constrain retries and eliminate backoff sleeps
        with patch.dict(
            "os.environ",
            {"BEDROCK_MAX_ATTEMPTS": "1", "BEDROCK_BACKOFF_BASE": "0", "BEDROCK_BACKOFF_CAP": "0"},
            clear=False,
        ):
            with patch.object(bedrock_client, "_bedrock_client") as mock_client:
                mock_client.converse.side_effect = client_error

                with pytest.raises(PlatformHTTPError) as exc_info:
                    await bedrock_client.generate_response(bedrock_prompt, "claude-3-5-sonnet")

            assert exc_info.value.response.code == "too_many_requests"

    @pytest.mark.asyncio
    async def test_generate_stream_response_error_handling(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test error handling in generate_stream_response method."""
        bedrock_prompt = BedrockPrompt()

        # Mock the boto3 client to raise an exception
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                },
            },
            operation_name="converse_stream",
        )

        # Use a real model from the existing model map
        # Speed up test: constrain retries and eliminate backoff sleeps
        with patch.dict(
            "os.environ",
            {"BEDROCK_MAX_ATTEMPTS": "1", "BEDROCK_BACKOFF_BASE": "0", "BEDROCK_BACKOFF_CAP": "0"},
            clear=False,
        ):
            with patch.object(bedrock_client, "_bedrock_client") as mock_client:
                mock_client.converse_stream.side_effect = client_error

                with pytest.raises(StreamingError) as exc_info:
                    async for _ in bedrock_client.generate_stream_response(
                        bedrock_prompt, "claude-3-5-sonnet"
                    ):
                        pass  # This shouldn't execute due to the exception

            assert exc_info.value.response.code == "forbidden"

    @pytest.mark.asyncio
    async def test_create_embeddings_error_handling(self, bedrock_client: BedrockClient) -> None:
        """Test error handling in create_embeddings method."""
        # Mock the boto3 client to raise an exception
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid model parameters",
                },
            },
            operation_name="invoke_model",
        )

        # Use a real embedding model from the existing model map
        with patch.object(bedrock_client, "_bedrock_client") as mock_client:
            mock_client.invoke_model.side_effect = client_error

            with pytest.raises(PlatformHTTPError) as exc_info:
                await bedrock_client.create_embeddings(["test text"], "titan-embed-text-v2")

            assert exc_info.value.response.code == "bad_request"

    @pytest.mark.asyncio
    async def test_create_embeddings_value_error_passthrough(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test that ValueError for unsupported models is not caught by error handler."""
        # Use a model that exists in the model map but will trigger ValueError
        # The claude models don't start with known embedding prefixes, so they'll raise ValueError
        with pytest.raises(ValueError, match="not a supported embedding model"):
            await bedrock_client.create_embeddings(["test text"], "claude-3-5-sonnet")


class TestBedrockClient:
    """Tests for the Bedrock client."""

    @pytest.fixture
    def mock_boto3_client(self) -> MagicMock:
        # Use AsyncMock for the service operations so they can be awaited by the
        # async Bedrock client implementation.
        mock_client = MagicMock(name="MockBedrockRuntimeClient")

        # ------------------------------------------------------------
        # `converse` --- single shot response
        # ------------------------------------------------------------
        mock_client.converse = AsyncMock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "test response"}],
                },
            },
            "usage": {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30},
            "metrics": {"latencyMs": 500},
        }

        # ------------------------------------------------------------
        # `converse_stream` --- streamed SSE/HTTP2 response
        # ------------------------------------------------------------

        async def _async_stream():  # type: ignore[return-type]
            events = [
                {
                    "chunk": {
                        "bytes": (b'{"type":"message_start","message":{"role":"assistant"}}'),
                    },
                },
                {
                    "chunk": {
                        "bytes": (
                            b'{"type":"content_block_start","index":0,"content_block"'
                            b':{"type":"text"}}'
                        ),
                    },
                },
                {
                    "chunk": {
                        "bytes": (
                            b'{"type":"content_block_delta","index":0,"delta":{"type"'
                            b':"text_delta","text":"test "}}'
                        ),
                    },
                },
                {
                    "chunk": {
                        "bytes": (
                            b'{"type":"content_block_delta","index":0,"delta":{"type"'
                            b':"text_delta","text":"response"}}'
                        ),
                    },
                },
                {"chunk": {"bytes": b'{"type":"message_stop"}'}},
                {
                    "chunk": {
                        "bytes": (
                            b'{"type":"metadata","usage":{"input_tokens":10,"output_'
                            b'tokens":20,"total_tokens":30},"metrics":{"latency_ms":'
                            b"500}}"
                        ),
                    },
                },
            ]
            for ev in events:
                yield ev

        mock_client.converse_stream = AsyncMock()
        mock_client.converse_stream.return_value = {
            "stream": _async_stream(),
            "ResponseMetadata": {
                "RequestId": "test-request-id",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Thu, 27 Feb 2025 18:52:25 GMT",
                    "content-type": "application/vnd.amazon.eventstream",
                    "transfer-encoding": "chunked",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "test-request-id",
                },
                "RetryAttempts": 0,
            },
        }

        # ------------------------------------------------------------
        # `invoke_model` --- embeddings endpoint
        # ------------------------------------------------------------
        mock_client.invoke_model = AsyncMock()

        return mock_client

    @pytest.fixture
    def kernel(self) -> Kernel:
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> BedrockPlatformParameters:
        return BedrockPlatformParameters(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )

    @pytest.fixture
    def bedrock_client(
        self,
        kernel: Kernel,
        parameters: BedrockPlatformParameters,
        mock_boto3_client: MagicMock,
    ) -> BedrockClient:
        with patch("boto3.client", return_value=mock_boto3_client):
            client = BedrockClient(kernel=kernel, parameters=parameters)
            client._bedrock_client = mock_boto3_client

            mock_response = ResponseMessage(
                content=[ResponseTextContent(text="test response")],
                raw_response={},
                role="agent",
            )
            client.parsers.parse_response = MagicMock(return_value=mock_response)
            mock_delta = MagicMock(spec=GenericDelta)

            async def mock_aiter() -> AsyncGenerator[GenericDelta, None]:
                yield mock_delta

            client.parsers.parse_stream_event = AsyncMock()
            client.parsers.parse_stream_event.return_value = mock_aiter()

            async def _mock_get_available_models() -> dict[str, list[str]]:
                return {
                    "amazon": [
                        "amazon.titan-embed-text-v2:0:8k",
                        "amazon.titan-embed-text-v1:2:8k",
                    ],
                    "cohere": [
                        "cohere.embed-english-v3:0:512",
                        "cohere.embed-multilingual-v3:0:512",
                    ],
                    "anthropic": [
                        "anthropic.claude-sonnet-4-20250514-v1:0",
                        "anthropic.claude-opus-4-20250514-v1:0",
                        "anthropic.claude-3-7-sonnet-20250219-v1:0",
                        "anthropic.claude-3-5-sonnet-20241022-v2:0",
                        "anthropic.claude-3-haiku-20240307-v1:0",
                    ],
                }

            client.get_available_models = _mock_get_available_models
            return client

    @pytest.fixture
    def prompt(self) -> Prompt:
        return Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[PromptUserMessage([PromptTextContent("Hello, world!")])],
        )

    @pytest.fixture
    def bedrock_prompt(self) -> BedrockPrompt:
        return BedrockPrompt()

    def test_init(self, parameters: BedrockPlatformParameters) -> None:
        with patch("boto3.client"):
            client = BedrockClient(parameters=parameters)
            assert client.name == "bedrock"
            assert isinstance(client.converters, BedrockConverters)
            assert isinstance(client.parsers, BedrockParsers)
            assert isinstance(client.parameters, BedrockPlatformParameters)

    def test_init_with_config_params(
        self,
        parameters: BedrockPlatformParameters,
    ) -> None:
        # BedrockClient now uses aiobotocore only; ensure the async config is
        # built with the supplied params.
        parameters = parameters.model_copy(
            update={"config_params": {"read_timeout": 60}},
        )
        client = BedrockClient(parameters=parameters)
        assert client.parameters.config_params == {"read_timeout": 60}
        assert client._config.read_timeout == 60  # type: ignore[attr-defined]

    def test_init_clients(self, parameters: BedrockPlatformParameters) -> None:
        # The client no longer performs a synchronous boto3 call, simply
        # verify that instantiation succeeds with the correct parameters.
        client = BedrockClient(parameters=parameters)
        assert client._parameters.region_name == "us-west-2"
        assert client._parameters.aws_access_key_id == "test-access-key"
        assert client._parameters.aws_secret_access_key == "test-secret-key"

    def test_init_parameters_from_kwargs(self) -> None:
        # No synchronous boto3 call is triggered, but instantiation still
        # accepts raw kwargs.
        client = BedrockClient(
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
        )
        assert client.parameters.region_name == "us-west-2"
        assert client.parameters.aws_access_key_id == "test-access-key"
        assert client.parameters.aws_secret_access_key == "test-secret-key"

    def test_init_parameters_with_updates(
        self,
        parameters: BedrockPlatformParameters,
    ) -> None:
        # BedrockClient handles parameter overrides without touching boto3.
        client = BedrockClient(parameters=parameters, region_name="us-east-1")
        assert client.parameters.region_name == "us-east-1"
        assert client.parameters.aws_access_key_id == "test-access-key"
        assert client.parameters.aws_secret_access_key == "test-secret-key"

    @pytest.mark.asyncio
    @patch.object(
        BedrockPrompt,
        "as_platform_request",
        return_value={
            "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
            "system": "You are a helpful assistant.",
        },
    )
    async def test_generate_response(
        self,
        mock_as_platform_request: MagicMock,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        test_model_map = {
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        }
        with patch.object(
            BedrockModelMap,
            "model_aliases",
            test_model_map,
        ):
            response = await bedrock_client.generate_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            )
            mock_boto3_client.converse.assert_called_once()
            assert isinstance(response, ResponseMessage)
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "test response"

    @pytest.mark.asyncio
    @patch.object(
        BedrockPrompt,
        "as_platform_request",
        return_value={
            "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
            "system": "You are a helpful assistant.",
        },
    )
    async def test_generate_response_with_model_selector(
        self,
        mock_as_platform_request: MagicMock,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        test_model_map = {
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        }
        with patch.object(
            BedrockModelMap,
            "model_aliases",
            test_model_map,
        ):
            response = await bedrock_client.generate_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            )
            mock_boto3_client.converse.assert_called_once()
            assert isinstance(response, ResponseMessage)

    @pytest.mark.asyncio
    @patch.object(
        BedrockPrompt,
        "as_platform_request",
        return_value={
            "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
            "system": "You are a helpful assistant.",
            "stream": True,
        },
    )
    async def test_generate_stream_response(
        self,
        mock_as_platform_request: MagicMock,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        test_model_map = {
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        }

        async def mock_stream_generator(
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[GenericDelta, None]:
            yield MagicMock(spec=GenericDelta)

        with patch.object(
            BedrockModelMap,
            "model_aliases",
            test_model_map,
        ):

            async def _dummy_stream():
                yield {}

            mock_boto3_client.converse_stream.return_value = {"stream": _dummy_stream()}
            bedrock_client.parsers.parse_stream_event = mock_stream_generator

            deltas: list[GenericDelta] = []
            async for delta in bedrock_client.generate_stream_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            ):
                deltas.append(delta)
            mock_boto3_client.converse_stream.assert_called_once()
            assert len(deltas) > 0

    # We will bring this back when we remove ModelMap
    # @pytest.mark.asyncio
    # @patch.object(
    #     BedrockPrompt,
    #     "as_platform_request",
    #     return_value={
    #         "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    #         "messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
    #         "system": "You are a helpful assistant.",
    #         "stream": True,
    #     },
    # )
    # async def test_generate_stream_response_with_model_selector(
    #     self,
    #     mock_as_platform_request: MagicMock,
    #     bedrock_client: BedrockClient,
    #     bedrock_prompt: BedrockPrompt,
    #     mock_boto3_client: MagicMock,
    # ) -> None:
    #     test_model_map = {
    #         "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    #     }

    #     async def mock_stream_generator(
    #         *args: Any,
    #         **kwargs: Any,
    #     ) -> AsyncGenerator[GenericDelta, None]:
    #         yield MagicMock(spec=GenericDelta)

    #     with patch.object(
    #         BedrockModelMap,
    #         "model_aliases",
    #         test_model_map,
    #     ):

    #         async def _dummy_stream():
    #             yield {}

    #         mock_boto3_client.converse_stream.return_value = {"stream": _dummy_stream()}
    #         bedrock_client.parsers.parse_stream_event = mock_stream_generator

    #         deltas: list[GenericDelta] = []
    #         async for delta in bedrock_client.generate_stream_response(
    #             bedrock_prompt,
    #             "claude-3-5-sonnet",
    #         ):
    #             deltas.append(delta)
    #         mock_boto3_client.converse_stream.assert_called_once()
    #         assert len(deltas) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text_embedding_model",
        [
            "titan-embed-text-v2",
            "titan-embed-text-v1",
            "cohere-embed-english-v3",
            "cohere-embed-multilingual-v3",
        ],
    )
    async def test_create_text_embeddings(
        self,
        bedrock_client: BedrockClient,
        text_embedding_model: str,
        mock_boto3_client: MagicMock,
    ) -> None:
        if text_embedding_model.startswith("titan-embed-text"):
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {"embedding": [0.1, 0.2, 0.3], "inputTextTokenCount": 5},
            ).encode()
            mock_boto3_client.invoke_model.return_value = mock_response
        else:
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {
                    "embeddings": [[0.1, 0.2, 0.3]],
                    "texts": ["This is a test"],
                    "token_count": 5,
                },
            ).encode()
            mock_boto3_client.invoke_model.return_value = mock_response

        texts = ["This is a test"]
        result = await bedrock_client.create_embeddings(texts, text_embedding_model)

        assert isinstance(result, dict)
        assert "embeddings" in result
        assert "model" in result
        assert "usage" in result
        assert len(result["embeddings"]) == 1
        assert len(result["embeddings"][0]) == 3

        mock_boto3_client.invoke_model.assert_called_once()
        call_kwargs = mock_boto3_client.invoke_model.call_args[1]
        expected_model_id = BedrockModelMap.model_aliases[text_embedding_model]
        assert call_kwargs["modelId"] == expected_model_id

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text_embedding_model",
        [
            "titan-embed-text-v2",
            "titan-embed-text-v1",
            "cohere-embed-english-v3",
            "cohere-embed-multilingual-v3",
        ],
    )
    async def test_create_text_embeddings_batch(
        self,
        bedrock_client: BedrockClient,
        text_embedding_model: str,
        mock_boto3_client: MagicMock,
    ) -> None:
        texts = ["First text", "Second text"]

        if text_embedding_model.startswith("titan-embed-text"):
            mock_response1 = {"body": MagicMock()}
            mock_response1["body"].read.return_value = json.dumps(
                {"embedding": [0.1, 0.2, 0.3], "inputTextTokenCount": 5},
            ).encode()
            mock_response2 = {"body": MagicMock()}
            mock_response2["body"].read.return_value = json.dumps(
                {"embedding": [0.4, 0.5, 0.6], "inputTextTokenCount": 3},
            ).encode()
            mock_boto3_client.invoke_model.side_effect = [
                mock_response1,
                mock_response2,
            ]
        else:
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {
                    "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                    "texts": texts,
                    "token_count": 8,
                },
            ).encode()
            mock_boto3_client.invoke_model.return_value = mock_response

        result = await bedrock_client.create_embeddings(texts, text_embedding_model)
        assert isinstance(result, dict)
        assert "embeddings" in result
        assert len(result["embeddings"]) == 2

        if text_embedding_model.startswith("titan-embed-text"):
            assert mock_boto3_client.invoke_model.call_count == 2
            assert result["embeddings"][0] == [0.1, 0.2, 0.3]
            assert result["embeddings"][1] == [0.4, 0.5, 0.6]
            assert result["usage"]["total_tokens"] == 8
        else:
            assert mock_boto3_client.invoke_model.call_count == 1
            assert result["embeddings"][0] == [0.1, 0.2, 0.3]
            assert result["embeddings"][1] == [0.4, 0.5, 0.6]
            assert result["usage"]["total_tokens"] == 8

    # This will be brought back in a follow-on, when we're ready to remove the old model map
    # @pytest.mark.asyncio
    # async def test_create_embeddings_with_model_selector(
    #     self,
    #     bedrock_client: BedrockClient,
    #     mock_boto3_client: MagicMock,
    # ) -> None:
    #     model_selector = DefaultModelSelector()
    #     text_embedding_model = model_selector.select_model(
    #         bedrock_client,
    #         ModelSelectionRequest(model_type="embedding"),
    #     )

    #     if text_embedding_model.endswith("titan-embed-text-v2"):
    #         mock_response = {"body": MagicMock()}
    #         mock_response["body"].read.return_value = json.dumps(
    #             {"embedding": [0.1, 0.2, 0.3], "inputTextTokenCount": 5},
    #         ).encode()
    #     else:
    #         mock_response = {"body": MagicMock()}
    #         mock_response["body"].read.return_value = json.dumps(
    #             {
    #                 "embeddings": [[0.1, 0.2, 0.3]],
    #                 "texts": ["This is a test"],
    #                 "token_count": 5,
    #             },
    #         ).encode()

    #     mock_boto3_client.invoke_model.return_value = mock_response
    #     texts = ["This is a test"]
    #     result = await bedrock_client.create_embeddings(texts, text_embedding_model)

    #     assert text_embedding_model == "titan-embed-text-v2"
    #     assert isinstance(result, dict)
    #     assert "embeddings" in result
    #     assert len(result["embeddings"]) == 1
