"""Unit tests for the OpenAI platform client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.openai.client import OpenAIClient
from agent_platform.core.platforms.openai.configs import OpenAIModelMap
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage


class MockChatCompletions:
    """Mock chat completions API."""

    def __init__(self):
        self.create = AsyncMock()
        self.completions = self


class MockEmbeddings:
    """Mock embeddings API."""

    def __init__(self):
        self.create = AsyncMock()


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self):
        """Initialize the mock client."""
        self.chat = MockChatCompletions()
        self.embeddings = MockEmbeddings()


class TestOpenAIClient:
    """Tests for the OpenAI client."""

    @pytest.fixture
    def mock_openai_client(self) -> Any:
        """Create a mock OpenAI client."""
        client = MockOpenAIClient()

        # Set up chat completions response
        async def mock_chat_response(**kwargs):
            if kwargs.get("stream", False):
                # Return a list that can be iterated over for streaming
                return [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": "Hello, ",
                                },
                            },
                        ],
                    },
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": "world!",
                                },
                            },
                        ],
                    },
                ]
            else:
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hello, world!",
                            },
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                }

        client.chat.completions.create.side_effect = mock_chat_response

        # Set up embeddings response
        async def mock_embeddings_response(**kwargs):
            return {
                "data": [
                    {"embedding": [0.1, 0.2, 0.3]} for _ in kwargs.get("input", [])
                ],
                "usage": {
                    "total_tokens": len(kwargs.get("input", [])) * 10,
                },
            }

        client.embeddings.create.side_effect = mock_embeddings_response

        return client

    @pytest.fixture
    def kernel(self) -> Kernel:
        """Create a mock kernel for testing."""
        return MagicMock(spec=Kernel)

    @pytest.fixture
    def parameters(self) -> OpenAIPlatformParameters:
        """Create OpenAI platform parameters for testing."""
        return OpenAIPlatformParameters(
            api_key="test-api-key",
        )

    @pytest.fixture
    def openai_client(
        self,
        kernel: Kernel,
        parameters: OpenAIPlatformParameters,
        mock_openai_client: Any,
    ) -> OpenAIClient:
        """Create an OpenAI client for testing."""
        with patch("openai.OpenAI", return_value=mock_openai_client):
            client = OpenAIClient(
                kernel=kernel,
                parameters=parameters,
            )
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
    def openai_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Create an OpenAI prompt for testing."""
        return OpenAIPrompt(prompt=prompt)

    def test_init(self, parameters: OpenAIPlatformParameters) -> None:
        """Test client initialization."""
        with patch("openai.OpenAI") as mock_openai:
            client = OpenAIClient(parameters=parameters)
            assert client.parameters.api_key == "test-api-key"
            mock_openai.assert_called_once_with(
                api_key="test-api-key",
                organization=None,
                base_url="https://api.openai.com/v1",
            )

    def test_init_clients(self, parameters: OpenAIPlatformParameters) -> None:
        """Test client initialization with OpenAI client."""
        mock_client = MockOpenAIClient()
        with patch("openai.OpenAI", return_value=mock_client) as mock_openai:
            client = OpenAIClient(parameters=parameters)
            mock_openai.assert_called_once_with(
                api_key="test-api-key",
                organization=None,
                base_url="https://api.openai.com/v1",
            )
            assert isinstance(client._openai_client, MockOpenAIClient)

    def test_init_parameters_from_kwargs(self) -> None:
        """Test parameter initialization from kwargs."""
        with patch("openai.OpenAI"):
            client = OpenAIClient(api_key="test-api-key")
            assert client.parameters.api_key == "test-api-key"

    def test_init_parameters_with_updates(
        self,
        parameters: OpenAIPlatformParameters,
    ) -> None:
        """Test parameter initialization with updates."""
        with patch("openai.OpenAI"):
            client = OpenAIClient(parameters=parameters, api_key="new-api-key")
            assert client.parameters.api_key == "new-api-key"

    @pytest.mark.asyncio
    @patch.object(
        OpenAIPrompt,
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
        openai_client: OpenAIClient,
        openai_prompt: OpenAIPrompt,
        mock_openai_client: Any,
    ) -> None:
        """Test generating a response."""
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": OpenAIModelMap(
                model_id="gpt-4",
                model_name="GPT-4",
                context_window=8192,
                max_tokens=4096,
            ),
        }
        with patch(
            "agent_platform.core.platforms.openai.configs.OpenAIPlatformConfigs.model_maps",
            new_callable=PropertyMock,
            return_value=test_model_map,
        ):
            response = await openai_client.generate_response(
                prompt=openai_prompt,
                model="gpt-4",
            )

            assert isinstance(response, ResponseMessage)
            assert len(response.content) == 1
            assert isinstance(response.content[0], ResponseTextContent)
            assert response.content[0].text == "Hello, world!"
            assert response.usage.total_tokens == 30

    @pytest.mark.asyncio
    @patch.object(
        OpenAIPrompt,
        "as_platform_request",
        return_value={
            "model": "gpt-4",
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
        openai_client: OpenAIClient,
        openai_prompt: OpenAIPrompt,
        mock_openai_client: Any,
    ) -> None:
        """Test generating a stream response."""
        # Add the model to the model maps
        test_model_map = {
            "gpt-4": OpenAIModelMap(
                model_id="gpt-4",
                model_name="GPT-4",
                context_window=8192,
                max_tokens=4096,
            ),
        }
        with patch(
            "agent_platform.core.platforms.openai.configs.OpenAIPlatformConfigs.model_maps",
            new_callable=PropertyMock,
            return_value=test_model_map,
        ):
            responses = []
            async for delta in openai_client.generate_stream_response(
                prompt=openai_prompt,
                model="gpt-4",
            ):
                responses.append(delta)

            assert len(responses) > 0
            assert all(hasattr(r, "op") for r in responses)

    @pytest.mark.asyncio
    async def test_create_embeddings(
        self,
        openai_client: OpenAIClient,
        mock_openai_client: Any,
    ) -> None:
        """Test creating embeddings."""
        # Add the embedding model to the model maps
        test_model_map = {
            "text-embedding-ada-002": OpenAIModelMap(
                model_id="text-embedding-ada-002",
                model_name="text-embedding-ada-002",
                context_window=8191,
                max_tokens=8191,
            ),
        }
        with patch(
            "agent_platform.core.platforms.openai.configs.OpenAIPlatformConfigs.model_maps",
            new_callable=PropertyMock,
            return_value=test_model_map,
        ):
            result = await openai_client.create_embeddings(
                texts=["Hello, world!"],
                model="text-embedding-ada-002",
            )

            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == 1
            assert len(result["embeddings"][0]) == 3
            assert "usage" in result
            assert result["usage"]["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_create_embeddings_batch(
        self,
        openai_client: OpenAIClient,
        mock_openai_client: Any,
    ) -> None:
        """Test creating embeddings in batch."""
        # Add the embedding model to the model maps
        test_model_map = {
            "text-embedding-ada-002": OpenAIModelMap(
                model_id="text-embedding-ada-002",
                model_name="text-embedding-ada-002",
                context_window=8191,
                max_tokens=8191,
            ),
        }
        with patch(
            "agent_platform.core.platforms.openai.configs.OpenAIPlatformConfigs.model_maps",
            new_callable=PropertyMock,
            return_value=test_model_map,
        ):
            result = await openai_client.create_embeddings(
                texts=["Hello, world!", "Goodbye, world!"],
                model="text-embedding-ada-002",
            )

            assert isinstance(result, dict)
            assert "embeddings" in result
            assert len(result["embeddings"]) == 2
            assert all(len(emb) == 3 for emb in result["embeddings"])
            assert "usage" in result
            assert result["usage"]["total_tokens"] == 20
