import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.client import BedrockClient
from agent_platform.core.platforms.bedrock.converters import BedrockConverters
from agent_platform.core.platforms.bedrock.parameters import BedrockPlatformParameters
from agent_platform.core.platforms.bedrock.parsers import BedrockParsers
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage


@pytest.fixture
def bedrock_parameters() -> BedrockPlatformParameters:
    return BedrockPlatformParameters(
        region_name="us-west-2",
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
    )


@pytest.fixture
def bedrock_client_factory(bedrock_parameters: BedrockPlatformParameters):
    def _factory() -> BedrockClient:
        with patch("aiobotocore.session.get_session"):
            return BedrockClient(parameters=bedrock_parameters)

    return _factory


@pytest.fixture(autouse=True)
def reset_bedrock_global_caches():
    BedrockClient._GLOBAL_MODEL_ARN_CACHE.clear()
    BedrockClient._GLOBAL_PROFILE_ARN_CACHE.clear()
    BedrockClient._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
    yield
    BedrockClient._GLOBAL_MODEL_ARN_CACHE.clear()
    BedrockClient._GLOBAL_PROFILE_ARN_CACHE.clear()
    BedrockClient._GLOBAL_AVAILABLE_MODELS_CACHE.clear()


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
        with patch("aiobotocore.session.get_session"):
            client = BedrockClient(parameters=parameters)

            async def mock_get_available_models():
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

            client.get_available_models = mock_get_available_models

            # Mock the _get_model_arn_from_local_model_id method to return the model ID as ARN
            async def mock_get_model_arn(model_id: str) -> str:
                return f"arn:aws:bedrock:us-west-2::foundation-model/{model_id}"

            client._get_model_arn_from_local_model_id = mock_get_model_arn
            return client

    def test_handle_bedrock_error_throttling_exception(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ThrottlingException."""
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            NoCredentialsError,
        )

        error = NoCredentialsError()

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unauthorized"
        assert "credentials" in result.response.message.lower()

    def test_handle_bedrock_error_connection_error(self, bedrock_client: BedrockClient) -> None:
        """Test handling of EndpointConnectionError."""
        from botocore.exceptions import (
            EndpointConnectionError,
        )

        error = EndpointConnectionError(endpoint_url="https://bedrock.us-west-2.amazonaws.com")

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "connect" in result.response.message.lower()

    def test_handle_bedrock_error_read_timeout(self, bedrock_client: BedrockClient) -> None:
        """Test handling of ReadTimeoutError."""
        from botocore.exceptions import (
            ReadTimeoutError,
        )

        error = ReadTimeoutError(endpoint_url="https://bedrock.us-west-2.amazonaws.com")

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "timed out" in result.response.message

    def test_handle_bedrock_error_botocore_connection_error(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of botocore ConnectionError."""
        from botocore.exceptions import (
            ConnectionError as BotocoreConnectionError,
        )

        error = BotocoreConnectionError(error=Exception("Connection failed"))

        result = bedrock_client._handle_bedrock_error(error, "claude-3-sonnet")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert "network connection" in result.response.message.lower()

    def test_handle_bedrock_error_generic_botocore_error(
        self, bedrock_client: BedrockClient
    ) -> None:
        """Test handling of generic BotoCoreError."""
        from botocore.exceptions import (
            BotoCoreError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        from botocore.exceptions import (
            ClientError,
        )

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
        with patch("aiobotocore.session.get_session"):
            client = BedrockClient(kernel=kernel, parameters=parameters)
            client._bedrock_client = mock_boto3_client

            # Mock the get_available_models method
            async def mock_get_available_models():
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

            client.get_available_models = mock_get_available_models

            # Mock the _get_model_arn_from_local_model_id method to return the model ID as ARN
            async def mock_get_model_arn(model_id: str) -> str:
                return f"arn:aws:bedrock:us-west-2::foundation-model/{model_id}"

            client._get_model_arn_from_local_model_id = mock_get_model_arn

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
        with patch("aiobotocore.session.get_session"):
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
            "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
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
            "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
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
        async def mock_stream_generator(
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[GenericDelta, None]:
            yield MagicMock(spec=GenericDelta)

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
        if "cohere" in text_embedding_model:
            assert text_embedding_model.replace("cohere-", "cohere.") in call_kwargs["modelId"]
        else:
            assert text_embedding_model in call_kwargs["modelId"]

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


@pytest.mark.asyncio
async def test_get_model_arn_returns_cached_value(
    bedrock_client_factory,
):
    client = bedrock_client_factory()
    client._model_arn_cache["anthropic.test-model"] = "arn:cached"
    control_client = MagicMock()
    control_client.list_inference_profiles = AsyncMock()
    control_client.list_foundation_models = AsyncMock()
    client._bedrock_control_plane_client = control_client

    arn = await client._get_model_arn_from_local_model_id("anthropic.test-model")

    assert arn == "arn:cached"
    control_client.list_inference_profiles.assert_not_awaited()
    control_client.list_foundation_models.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_model_arn_uses_global_profile_cache(
    bedrock_client_factory,
):
    profile_id = "profile/anthropic.test-model"
    BedrockClient._GLOBAL_PROFILE_ARN_CACHE[profile_id] = "arn:profile"

    client = bedrock_client_factory()
    control_client = MagicMock()
    control_client.list_inference_profiles = AsyncMock()
    control_client.list_foundation_models = AsyncMock()
    client._bedrock_control_plane_client = control_client

    arn = await client._get_model_arn_from_local_model_id("anthropic.test-model")

    assert arn == "arn:profile"
    assert client._model_arn_cache["anthropic.test-model"] == "arn:profile"
    assert BedrockClient._GLOBAL_MODEL_ARN_CACHE["anthropic.test-model"] == "arn:profile"
    control_client.list_inference_profiles.assert_not_awaited()
    control_client.list_foundation_models.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_model_arn_falls_back_to_foundation_models(
    bedrock_client_factory,
):
    client = bedrock_client_factory()
    control_client = MagicMock()
    control_client.list_inference_profiles = AsyncMock(
        return_value={"inferenceProfileSummaries": []},
    )
    control_client.list_foundation_models = AsyncMock(
        return_value={
            "modelSummaries": [
                {
                    "modelId": "anthropic.test-model",
                    "modelArn": "arn:foundation",
                },
            ],
        },
    )
    client._bedrock_control_plane_client = control_client

    arn = await client._get_model_arn_from_local_model_id("anthropic.test-model")

    assert arn == "arn:foundation"
    assert client._model_arn_cache["anthropic.test-model"] == "arn:foundation"
    assert BedrockClient._GLOBAL_MODEL_ARN_CACHE["anthropic.test-model"] == "arn:foundation"
    control_client.list_inference_profiles.assert_awaited()
    control_client.list_foundation_models.assert_awaited()


@pytest.mark.asyncio
async def test_get_available_models_caches_per_instance(
    bedrock_client_factory,
):
    client = bedrock_client_factory()
    control_client = MagicMock()
    control_client.list_foundation_models = AsyncMock(
        return_value={
            "modelSummaries": [
                {"providerName": "Anthropic", "modelId": "anthropic.test-model"},
            ],
        },
    )
    client._bedrock_control_plane_client = control_client

    first = await client.get_available_models()
    second = await client.get_available_models()

    expected = {"anthropic": ["anthropic.test-model"]}
    assert first == expected
    assert second == expected
    assert control_client.list_foundation_models.await_count == 1


@pytest.mark.asyncio
async def test_get_available_models_warms_global_cache_for_new_instance(
    bedrock_client_factory,
):
    client_a = bedrock_client_factory()
    control_client_a = MagicMock()
    control_client_a.list_foundation_models = AsyncMock(
        return_value={
            "modelSummaries": [
                {"providerName": "Anthropic", "modelId": "anthropic.test-model"},
            ],
        },
    )
    client_a._bedrock_control_plane_client = control_client_a

    await client_a.get_available_models()
    assert control_client_a.list_foundation_models.await_count == 1
    assert BedrockClient._GLOBAL_AVAILABLE_MODELS_CACHE == {"anthropic": ["anthropic.test-model"]}

    client_b = bedrock_client_factory()
    control_client_b = MagicMock()
    control_client_b.list_foundation_models = AsyncMock(
        side_effect=AssertionError("global cache should avoid refetch"),
    )
    client_b._bedrock_control_plane_client = control_client_b

    models = await client_b.get_available_models()

    assert models == {"anthropic": ["anthropic.test-model"]}
    control_client_b.list_foundation_models.assert_not_called()
