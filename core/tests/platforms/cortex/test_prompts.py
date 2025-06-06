import pytest

from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.platforms.cortex.types import (
    CortexPromptContent,
    CortexPromptMessage,
    CortexPromptToolResults,
    CortexPromptToolSpec,
    CortexPromptToolUse,
)


class TestCortexPrompt:
    """Tests for the Snowflake Cortex prompt."""

    @pytest.fixture
    def cortex_prompt(self) -> CortexPrompt:
        """Create a basic Cortex prompt for testing."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="system",
                    content="You are a helpful assistant.",
                ),
                CortexPromptMessage(
                    role="user",
                    content="Hello, world!",
                ),
            ],
            top_p=1.0,
            temperature=0.0,
            max_tokens=1024,
        )

    @pytest.fixture
    def cortex_prompt_with_tools(self) -> CortexPrompt:
        """Create a Cortex prompt with tools for testing."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="system",
                    content="You are a helpful assistant.",
                ),
                CortexPromptMessage(
                    role="user",
                    content="Use the tool to get the weather.",
                ),
            ],
            tools=[
                CortexPromptToolSpec(
                    name="get_weather",
                    description="Get the weather for a location",
                    input_schema={
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                ),
            ],
        )

    @pytest.fixture
    def cortex_prompt_only_user(self) -> CortexPrompt:
        """Create a Cortex prompt with only a user message."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="user",
                    content="Just a user message.",
                ),
            ],
        )

    @pytest.fixture
    def cortex_prompt_only_system(self) -> CortexPrompt:
        """Create a Cortex prompt with only a system message."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="system",
                    content="System instruction only.",
                ),
            ],
        )

    @pytest.fixture
    def cortex_prompt_empty_messages(self) -> CortexPrompt:
        """Create a Cortex prompt with an empty messages list."""
        return CortexPrompt(messages=[])

    @pytest.fixture
    def cortex_prompt_none_messages(self) -> CortexPrompt:
        """Create a Cortex prompt with messages=None."""
        return CortexPrompt(messages=None)

    @pytest.fixture
    def cortex_prompt_with_tool_use(self) -> CortexPrompt:
        """Create a Cortex prompt with tool use for testing."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="user",
                    content="What's the weather in London?",
                ),
                CortexPromptMessage(
                    role="assistant",
                    content="",  # Assistant message might be empty before tool use
                    content_list=[
                        CortexPromptContent(
                            type="tool_use",
                            tool_use=CortexPromptToolUse(
                                tool_use_id="toolu_123",
                                name="get_weather",
                                input={"location": "London"},
                            ),
                        ),
                    ],
                ),
            ],
            tools=[  # Tools must be present if tool_use is
                CortexPromptToolSpec(
                    name="get_weather",
                    description="Get weather",
                    input_schema={"type": "object", "properties": {}},
                ),
            ],
        )

    @pytest.fixture
    def cortex_prompt_with_tool_results(self) -> CortexPrompt:
        """Create a Cortex prompt with tool results for testing."""
        return CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="user",
                    content="What's the weather in London?",
                ),
                CortexPromptMessage(
                    role="assistant",
                    content="",
                    content_list=[
                        CortexPromptContent(
                            type="tool_use",
                            tool_use=CortexPromptToolUse(
                                tool_use_id="toolu_123",
                                name="get_weather",
                                input={"location": "London"},
                            ),
                        ),
                    ],
                ),
                CortexPromptMessage(
                    role="user",  # Tool results come back in user role for Cortex
                    content="Tool results:",  # Placeholder content often needed
                    content_list=[
                        CortexPromptContent(
                            type="tool_results",
                            tool_results=CortexPromptToolResults(
                                tool_use_id="toolu_123",
                                name="get_weather",
                                content=[
                                    CortexPromptContent(
                                        type="text",
                                        text='{"temperature": 15, "unit": "C"}',
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ],
            tools=[  # Tools must be present if tool_results are
                CortexPromptToolSpec(
                    name="get_weather",
                    description="Get weather",
                    input_schema={"type": "object", "properties": {}},
                ),
            ],
        )

    def test_as_platform_request_non_stream(
        self,
        cortex_prompt: CortexPrompt,
    ) -> None:
        """Test that as_platform_request works correctly for non-stream requests."""
        model_id = "claude-3-5-sonnet"

        request = cortex_prompt.as_platform_request(model_id)

        # Check the request structure
        assert request["model"] == model_id
        assert "messages" in request
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "Hello, world!",
            },
        ]
        assert "stream" in request
        assert not request["stream"]
        assert request["temperature"] == 0.0
        assert request["top_p"] == 1.0
        assert request["max_tokens"] == 1024
        assert "tools" not in request

    def test_as_platform_request_stream(self, cortex_prompt: CortexPrompt) -> None:
        """Test that as_platform_request works correctly for stream requests."""
        model_id = "claude-3-5-sonnet"

        request = cortex_prompt.as_platform_request(model_id, stream=True)

        # Check the request structure
        assert request["model"] == model_id
        assert "messages" in request
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "Hello, world!",
            },
        ]
        assert "stream" in request
        assert request["stream"]
        assert request["temperature"] == 0.0
        assert request["top_p"] == 1.0
        assert request["max_tokens"] == 1024
        assert "tools" not in request

    def test_as_platform_request_with_tools(
        self,
        cortex_prompt_with_tools: CortexPrompt,
    ) -> None:
        """Test that as_platform_request works correctly with tools."""
        model_id = "claude-3-5-sonnet"

        request = cortex_prompt_with_tools.as_platform_request(model_id)

        # Check the request structure
        assert request["model"] == model_id
        assert "messages" in request
        assert request["messages"] == [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "Use the tool to get the weather.",
            },
        ]
        assert "tools" in request
        assert request["tools"] == [
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                },
            },
        ]
        assert request["temperature"] == 0.0
        assert request["top_p"] == 1.0
        assert request["max_tokens"] == 4096

    def test_as_platform_request_with_additional_fields(self) -> None:
        """Test that as_platform_request works correctly with additional
        request fields."""
        prompt = CortexPrompt(
            messages=[
                CortexPromptMessage(
                    role="system",
                    content="You are a helpful assistant.",
                ),
                CortexPromptMessage(
                    role="user",
                    content="Hello, world!",
                ),
            ],
            temperature=0.7,
            top_p=0.9,
            max_tokens=1000,
        )

        model_id = "claude-3-5-sonnet"
        request = prompt.as_platform_request(model_id)

        # Check the additional fields
        assert "temperature" in request
        assert request["temperature"] == 0.7
        assert "top_p" in request
        assert request["top_p"] == 0.9
        assert "max_tokens" in request
        assert request["max_tokens"] == 1000
        assert "tools" not in request

    def test_as_platform_request_only_user(
        self,
        cortex_prompt_only_user: CortexPrompt,
    ) -> None:
        """Test request generation with only a user message."""
        model_id = "test-model"
        request = cortex_prompt_only_user.as_platform_request(model_id)
        assert request["model"] == model_id
        assert request["messages"] == [
            {"role": "user", "content": "Just a user message."},
        ]
        assert not request["stream"]
        assert "tools" not in request

    def test_as_platform_request_only_system(
        self,
        cortex_prompt_only_system: CortexPrompt,
    ) -> None:
        """Test request generation with only a system message."""
        model_id = "test-model"
        request = cortex_prompt_only_system.as_platform_request(model_id)
        assert request["model"] == model_id
        assert request["messages"] == [
            {"role": "system", "content": "System instruction only."},
        ]
        assert not request["stream"]
        assert "tools" not in request

    def test_as_platform_request_empty_messages(
        self,
        cortex_prompt_empty_messages: CortexPrompt,
    ) -> None:
        """Test request generation with an empty messages list."""
        model_id = "test-model"
        request = cortex_prompt_empty_messages.as_platform_request(model_id)
        assert request["model"] == model_id
        assert request["messages"] == []
        assert not request["stream"]
        assert "tools" not in request

    def test_as_platform_request_none_messages(
        self,
        cortex_prompt_none_messages: CortexPrompt,
    ) -> None:
        """Test request generation with messages=None."""
        model_id = "test-model"
        request = cortex_prompt_none_messages.as_platform_request(model_id)
        assert request["model"] == model_id
        assert request["messages"] == []
        assert not request["stream"]
        assert "tools" not in request

    def test_as_platform_request_zero_temp_max_tokens(self) -> None:
        """Test request generation with zero temperature and max_tokens."""
        prompt = CortexPrompt(
            messages=[CortexPromptMessage(role="user", content="Test")],
            temperature=0.0,
            max_tokens=0,
            top_p=1.0,
        )
        model_id = "test-model"
        request = prompt.as_platform_request(model_id)
        assert request["model"] == model_id
        assert request["temperature"] == 0.0
        assert request["max_tokens"] == 0
        assert request["top_p"] == 1.0
        assert not request["stream"]
        assert "tools" not in request

    def test_as_platform_request_none_tools(self) -> None:
        """Test request generation with tools=None."""
        prompt = CortexPrompt(
            messages=[CortexPromptMessage(role="user", content="Test")],
            tools=None,
        )
        model_id = "test-model"
        request = prompt.as_platform_request(model_id)
        assert request["model"] == model_id
        assert "tools" not in request
        assert request["temperature"] == 0.0
        assert request["top_p"] == 1.0
        assert request["max_tokens"] == 4096

    def test_as_platform_request_with_tool_use(
        self,
        cortex_prompt_with_tool_use: CortexPrompt,
    ) -> None:
        """Test request generation with tool use content."""
        model_id = "test-model-tool-use"
        request = cortex_prompt_with_tool_use.as_platform_request(model_id)

        assert request["model"] == model_id
        assert "messages" in request
        assert len(request["messages"]) == 2
        assert request["messages"][0] == {
            "role": "user",
            "content": "What's the weather in London?",
        }
        assert request["messages"][1] == {
            "role": "assistant",
            "content": "",
            "content_list": [
                {
                    "type": "tool_use",
                    "tool_use": {
                        "tool_use_id": "toolu_123",
                        "name": "get_weather",
                        "input": {"location": "London"},
                    },
                },
            ],
        }
        assert "tools" in request  # Tools must be present
        assert len(request["tools"]) == 1
        assert request["tools"][0]["tool_spec"]["name"] == "get_weather"
        assert not request["stream"]

    def test_as_platform_request_with_tool_results(
        self,
        cortex_prompt_with_tool_results: CortexPrompt,
    ) -> None:
        """Test request generation with tool results content."""
        model_id = "test-model-tool-results"
        request = cortex_prompt_with_tool_results.as_platform_request(model_id)

        assert request["model"] == model_id
        assert "messages" in request
        assert len(request["messages"]) == 3
        # Check assistant message with tool use
        assert request["messages"][1]["role"] == "assistant"
        assert request["messages"][1]["content_list"][0]["type"] == "tool_use"
        # Check user message with tool results
        assert request["messages"][2]["role"] == "user"
        assert request["messages"][2]["content"] == "Tool results:"
        assert request["messages"][2]["content_list"][0]["type"] == "tool_results"
        assert request["messages"][2]["content_list"][0]["tool_results"] == {
            "tool_use_id": "toolu_123",
            "name": "get_weather",
            "content": [
                {"type": "text", "text": '{"temperature": 15, "unit": "C"}'},
            ],
        }
        assert "tools" in request  # Tools must be present
        assert len(request["tools"]) == 1
        assert not request["stream"]
