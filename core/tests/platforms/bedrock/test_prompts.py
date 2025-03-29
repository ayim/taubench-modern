import pytest

from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt


class TestBedrockPrompt:
    """Tests for the Bedrock prompt."""

    @pytest.fixture
    def bedrock_prompt(self) -> BedrockPrompt:
        """Create a basic Bedrock prompt for testing."""
        return BedrockPrompt(
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Hello, world!"}],
                },
            ],
            system=[{"text": "You are a helpful assistant."}],
        )

    @pytest.fixture
    def bedrock_prompt_with_tools(self) -> BedrockPrompt:
        """Create a Bedrock prompt with tools for testing."""
        return BedrockPrompt(
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Use the tool to get the weather."}],
                },
            ],
            system=[{"text": "You are a helpful assistant."}],
            tool_config={
                "tools": [
                    {
                        "toolSpec": {
                            "name": "get_weather",
                            "description": "Get the weather for a location",
                            "inputSchema": {
                                "json": {
                                    "type": "object",
                                    "properties": {
                                        "location": {"type": "string"},
                                    },
                                    "required": ["location"],
                                },
                            },
                        },
                    },
                ],
                "toolChoice": {"auto": {}},
            },
        )

    def test_as_platform_request_non_stream(
        self,
        bedrock_prompt: BedrockPrompt,
    ) -> None:
        """Test that as_platform_request works correctly for non-stream requests."""
        model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

        request = bedrock_prompt.as_platform_request(model_id)

        # Check the request structure
        assert request["modelId"] == model_id
        assert request["messages"] == [
            {
                "role": "user",
                "content": [{"text": "Hello, world!"}],
            },
        ]
        assert request["system"] == [{"text": "You are a helpful assistant."}]
        assert "stream" not in request

    def test_as_platform_request_stream(self, bedrock_prompt: BedrockPrompt) -> None:
        """Test that as_platform_request works correctly for stream requests."""
        model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

        request = bedrock_prompt.as_platform_request(model_id, stream=True)

        # Check the request structure
        assert request["modelId"] == model_id
        assert request["messages"] == [
            {
                "role": "user",
                "content": [{"text": "Hello, world!"}],
            },
        ]
        assert request["system"] == [{"text": "You are a helpful assistant."}]

    def test_as_platform_request_with_tools(
        self,
        bedrock_prompt_with_tools: BedrockPrompt,
    ) -> None:
        """Test that as_platform_request works correctly with tools."""
        model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

        request = bedrock_prompt_with_tools.as_platform_request(model_id)

        # Check the request structure
        assert request["modelId"] == model_id
        assert request["messages"] == [
            {
                "role": "user",
                "content": [{"text": "Use the tool to get the weather."}],
            },
        ]
        assert request["system"] == [{"text": "You are a helpful assistant."}]
        assert request["toolConfig"] == {
            "tools": [
                {
                    "toolSpec": {
                        "name": "get_weather",
                        "description": "Get the weather for a location",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                },
                                "required": ["location"],
                            },
                        },
                    },
                },
            ],
            "toolChoice": {"auto": {}},
        }

    def test_as_platform_request_with_additional_fields(self) -> None:
        """Test that as_platform_request works correctly with additional
        request fields."""
        prompt = BedrockPrompt(
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Hello, world!"}],
                },
            ],
            system=[{"text": "You are a helpful assistant."}],
            additional_model_request_fields={
                "temperature": 0.7,
                "maxTokens": 1000,
            },
        )

        model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        request = prompt.as_platform_request(model_id)

        # Check the additional fields
        assert request["additionalModelRequestFields"] == {
            "temperature": 0.7,
            "maxTokens": 1000,
        }
