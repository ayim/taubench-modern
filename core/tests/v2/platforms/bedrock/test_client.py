import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_server_types_v2.delta import GenericDelta
from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.platforms.bedrock.client import BedrockClient
from agent_server_types_v2.platforms.bedrock.configs import BedrockModelMap
from agent_server_types_v2.platforms.bedrock.converters import BedrockConverters
from agent_server_types_v2.platforms.bedrock.parameters import BedrockPlatformParameters
from agent_server_types_v2.platforms.bedrock.parsers import BedrockParsers
from agent_server_types_v2.platforms.bedrock.prompts import BedrockPrompt
from agent_server_types_v2.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_server_types_v2.responses.content.text import ResponseTextContent
from agent_server_types_v2.responses.response import ResponseMessage


class MockBedrockRuntimeClient:
    """Mock AWS Bedrock Runtime client for testing."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Mock converse method."""
        return {
            "system": "",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "test message"}],
                },
                {
                    "role": "assistant",
                    "content": [{"text": "test response"}],
                },
            ],
        }

    def converse_stream(self, **kwargs: Any) -> dict[str, Any]:
        """Mock converse_stream method."""

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


class TestBedrockClient:
    """Tests for the Bedrock client."""

    @pytest.fixture
    def mock_boto3_client(self) -> MagicMock:
        """Create a mock boto3 client for testing."""
        mock_client = MagicMock(name="MockBedrockRuntimeClient")

        # Set up the mock response for converse
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "test response",
                        },
                    ],
                },
            },
            "usage": {
                "inputTokens": 10,
                "outputTokens": 20,
                "totalTokens": 30,
            },
            "metrics": {
                "latencyMs": 500,
            },
        }

        # Set up the mock stream response
        class MockStream:
            def __iter__(self):
                events = [
                    {
                        "chunk": {
                            "bytes": b'{"type":"message_start",'
                                b'"message":{"role":"assistant"}}',
                        },
                    },
                    {
                        "chunk": {
                            "bytes": b'{"type":"content_block_start","index":0,'
                                b'"content_block":{"type":"text"}}',
                        },
                    },
                    {
                        "chunk": {
                            "bytes": b'{"type":"content_block_delta","index":0,'
                                b'"delta":{"type":"text_delta","text":"test "}}',
                        },
                    },
                    {
                        "chunk": {
                            "bytes": b'{"type":"content_block_delta","index":0,'
                                b'"delta":{"type":"text_delta","text":"response"}}',
                        },
                    },
                    {
                        "chunk": {
                            "bytes": b'{"type":"message_stop"}',
                        },
                    },
                    {
                        "chunk": {
                            "bytes": (
                                b'{"type":"metadata","usage":{"input_tokens":10,'
                                b'"output_tokens":20,"total_tokens":30},'
                                b'"metrics":{"latency_ms":500}}'
                            ),
                        },
                    },
                ]
                yield from events

        mock_client.converse_stream.return_value = {
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

        return mock_client

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> BedrockPlatformParameters:
        """Create Bedrock platform parameters for testing."""
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
        """Create a Bedrock client for testing with mocked boto3 client."""
        with patch("boto3.client", return_value=mock_boto3_client):
            client = BedrockClient(kernel=kernel, parameters=parameters)
            client._bedrock_runtime_client = mock_boto3_client

            # Create a mock response
            mock_response = ResponseMessage(
                content=[ResponseTextContent(text="test response")],
                raw_response={},
                role="agent",
            )

            # Patch the parse_response method
            client.parsers.parse_response = MagicMock(return_value=mock_response)

            # For streaming tests - create a proper async iterator
            mock_delta = MagicMock(spec=GenericDelta)

            async def mock_aiter():
                yield mock_delta

            client.parsers.parse_stream_event = AsyncMock()
            client.parsers.parse_stream_event.return_value = mock_aiter()

            return client

    @pytest.fixture
    def prompt(self) -> Prompt:
        """Create a prompt for testing."""
        return Prompt(
            system_instruction="You are a helpful assistant.",
            messages=[
                PromptUserMessage(
                    content=[PromptTextContent(text="Hello, world!")],
                ),
            ],
        )

    @pytest.fixture
    def bedrock_prompt(
        self,
        bedrock_client: BedrockClient,
        prompt: Prompt,
    ) -> BedrockPrompt:
        """Create a Bedrock prompt for testing."""
        mock_bedrock_prompt = MagicMock(spec=BedrockPrompt)
        mock_bedrock_prompt.as_platform_request.return_value = {
            "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Hello, world!"}],
                },
            ],
            "system": "You are a helpful assistant.",
        }

        # Mock the convert_prompt method
        with patch.object(
            bedrock_client.converters,
            "convert_prompt",
            return_value=mock_bedrock_prompt,
        ):
            return mock_bedrock_prompt

    def test_init(self, parameters: BedrockPlatformParameters) -> None:
        """Test that the Bedrock client initializes correctly."""
        with patch("boto3.client"):
            client = BedrockClient(parameters=parameters)

            assert client.name == "bedrock"
            assert isinstance(client.converters, BedrockConverters)
            assert isinstance(client.parsers, BedrockParsers)
            assert isinstance(client.parameters, BedrockPlatformParameters)

    def test_init_clients(self, parameters: BedrockPlatformParameters) -> None:
        """Test that the Bedrock client initializes the boto3 client correctly."""
        with patch("boto3.client") as mock_boto3_client:
            BedrockClient(parameters=parameters)

            mock_boto3_client.assert_called_once_with(
                "bedrock-runtime",
                region_name="us-west-2",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            )

    def test_init_parameters_from_kwargs(self) -> None:
        """Test that the Bedrock client initializes parameters from kwargs."""
        with patch("boto3.client"):
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
        """Test that the Bedrock client initializes parameters with updates."""
        with patch("boto3.client"):
            client = BedrockClient(
                parameters=parameters,
                region_name="us-east-1",  # Override the region
            )

            assert client.parameters.region_name == "us-east-1"
            assert client.parameters.aws_access_key_id == "test-access-key"
            assert client.parameters.aws_secret_access_key == "test-secret-key"

    @pytest.mark.asyncio
    async def test_generate_response(
        self,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        """Test that the Bedrock client generates a response correctly."""
        # Create a test model map and use it directly
        test_model_map = {
            "claude-3-5-sonnet": (
                "anthropic.claude-3-5-sonnet-20240620-v1:0"
            ),
        }

        # Mock BedrockModelMap.__class_getitem__ to return our test map
        with patch.object(
            BedrockModelMap,
            "__class_getitem__",
            return_value=test_model_map,
        ):
            # Update the mock to accept the expected argument
            bedrock_prompt.as_platform_request.reset_mock()

            response = await bedrock_client.generate_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            )

            # Verify the bedrock runtime client was called
            assert bedrock_prompt.as_platform_request.called
            mock_boto3_client.converse.assert_called_once()

            # Verify the response was correctly parsed
            assert isinstance(response, ResponseMessage)

    @pytest.mark.asyncio
    async def test_generate_response_with_model_selector(
        self,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        """Test that the Bedrock client generates a response with a model selector."""
        # Create a test model map and use it directly
        test_model_map = {
            "claude-3-5-sonnet": (
                "anthropic.claude-3-5-sonnet-20240620-v1:0"
            ),
        }

        # Mock BedrockModelMap.__class_getitem__ to return our test map
        with patch.object(
            BedrockModelMap,
            "__class_getitem__",
            return_value=test_model_map,
        ):
            # Update the mock to accept the expected argument
            bedrock_prompt.as_platform_request.reset_mock()

            response = await bedrock_client.generate_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            )

            # Verify the bedrock runtime client was called
            assert bedrock_prompt.as_platform_request.called
            mock_boto3_client.converse.assert_called_once()

            # Verify the response was correctly parsed
            assert isinstance(response, ResponseMessage)

    @pytest.mark.asyncio
    async def test_generate_stream_response(
        self,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        """Test that the Bedrock client generates a stream response correctly."""
        # Create a test model map and use it directly
        test_model_map = {
            "claude-3-5-sonnet": (
                "anthropic.claude-3-5-sonnet-20240620-v1:0"
            ),
        }

        # Create a proper async generator for the mock
        async def mock_stream_generator(*args, **kwargs):
            yield MagicMock(spec=GenericDelta)

        # Mock BedrockModelMap.__class_getitem__ to return our test map
        with patch.object(
            BedrockModelMap,
            "__class_getitem__",
            return_value=test_model_map,
        ):
            # Update the mock to accept the expected argument
            bedrock_prompt.as_platform_request.reset_mock()

            # Mock the stream response from boto3
            mock_boto3_client.converse_stream.return_value = {"stream": [{}]}

            # Mock the parse_stream_event method to return our async generator
            bedrock_client.parsers.parse_stream_event = mock_stream_generator

            deltas = []
            async for delta in bedrock_client.generate_stream_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            ):
                deltas.append(delta)

            # Verify the bedrock runtime client was called
            assert bedrock_prompt.as_platform_request.called
            assert "stream" in bedrock_prompt.as_platform_request.call_args[1]
            assert bedrock_prompt.as_platform_request.call_args[1]["stream"] is True
            mock_boto3_client.converse_stream.assert_called_once()

            # Verify we got deltas
            assert len(deltas) > 0

    @pytest.mark.asyncio
    async def test_generate_stream_response_with_model_selector(
        self,
        bedrock_client: BedrockClient,
        bedrock_prompt: BedrockPrompt,
        mock_boto3_client: MagicMock,
    ) -> None:
        """Test that the Bedrock client generates a stream response
        with a model selector."""
        # Create a test model map and use it directly
        test_model_map = {
            "claude-3-5-sonnet": (
                "anthropic.claude-3-5-sonnet-20240620-v1:0"
            ),
        }

        # Create a proper async generator for the mock
        async def mock_stream_generator(*args, **kwargs):
            yield MagicMock(spec=GenericDelta)

        # Mock BedrockModelMap.__class_getitem__ to return our test map
        with patch.object(
            BedrockModelMap,
            "__class_getitem__",
            return_value=test_model_map,
        ):
            # Update the mock to accept the expected argument
            bedrock_prompt.as_platform_request.reset_mock()

            # Mock the stream response from boto3
            mock_boto3_client.converse_stream.return_value = {"stream": [{}]}

            # Mock the parse_stream_event method to return our async generator
            bedrock_client.parsers.parse_stream_event = mock_stream_generator

            deltas = []
            async for delta in bedrock_client.generate_stream_response(
                bedrock_prompt,
                "claude-3-5-sonnet",
            ):
                deltas.append(delta)

            # Verify the bedrock runtime client was called
            assert bedrock_prompt.as_platform_request.called
            assert "stream" in bedrock_prompt.as_platform_request.call_args[1]
            assert bedrock_prompt.as_platform_request.call_args[1]["stream"] is True
            mock_boto3_client.converse_stream.assert_called_once()

            # Verify we got deltas
            assert len(deltas) > 0
