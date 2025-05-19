import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.model_selector import (
    DefaultModelSelector,
    ModelSelectionRequest,
)
from agent_platform.core.model_selector.default import ModelMappingConfig
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


class TestBedrockClient:
    """Tests for the Bedrock client."""

    @pytest.fixture
    def mock_boto3_client(self) -> MagicMock:
        mock_client = MagicMock(name="MockBedrockRuntimeClient")
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

        class MockStream:
            def __iter__(self):
                events = [
                    {
                        "chunk": {
                            "bytes": (
                                b'{"type":"message_start","message":{"role":"assistant"}}'
                            ),
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
            client._bedrock_runtime_client = mock_boto3_client

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
        with patch("boto3.client") as mock_client:
            parameters = parameters.model_copy(
                update={"config_params": {"read_timeout": 60}},
            )
            client = BedrockClient(parameters=parameters)
            assert client.parameters.config_params == {"read_timeout": 60}
            assert mock_client.call_args[1]["config"].read_timeout == 60

    def test_init_clients(self, parameters: BedrockPlatformParameters) -> None:
        with patch("boto3.client") as mock_boto3_client:
            BedrockClient(parameters=parameters)
            mock_boto3_client.assert_called_once_with(
                "bedrock-runtime",
                region_name="us-west-2",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            )

    def test_init_parameters_from_kwargs(self) -> None:
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
        with patch("boto3.client"):
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
            mock_boto3_client.converse_stream.return_value = {"stream": [{}]}
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
    async def test_generate_stream_response_with_model_selector(
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
            mock_boto3_client.converse_stream.return_value = {"stream": [{}]}
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

    @pytest.mark.asyncio
    async def test_create_embeddings_with_model_selector(
        self,
        bedrock_client: BedrockClient,
        mock_boto3_client: MagicMock,
    ) -> None:
        model_selector = DefaultModelSelector()
        text_embedding_model = model_selector.select_model(
            bedrock_client,
            ModelSelectionRequest(model_type="embedding", quality_tier="balanced"),
        )

        if text_embedding_model.startswith("titan-embed-text"):
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {"embedding": [0.1, 0.2, 0.3], "inputTextTokenCount": 5},
            ).encode()
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

        default_provider = bedrock_client.configs.default_platform_provider["embedding"]
        default_tier = bedrock_client.configs.default_quality_tier["embedding"]
        default_model = ModelMappingConfig().get_model_name(
            platform=bedrock_client.name,
            provider=default_provider,
            model_type="embedding",
            tier=default_tier,
        )
        assert text_embedding_model == default_model
        assert isinstance(result, dict)
        assert "embeddings" in result
        assert len(result["embeddings"]) == 1
