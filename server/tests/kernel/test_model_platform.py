"""Tests for the AgentServerPlatformInterface class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content import (
    PromptTextContent,
    PromptToolResultContent,
)
from agent_platform.core.prompts.messages import PromptAgentMessage, PromptUserMessage
from agent_platform.server.kernel.model_platform import AgentServerPlatformInterface


@pytest.fixture
def mock_platform_client():
    """Create a mock platform client for testing."""
    client = MagicMock()

    # Set up model context window for testing truncation
    client.model_map.model_context_windows = {"gpt-4": 8192}

    # Mock the generate_response method
    client.generate_response = AsyncMock()

    # Mock the converters for prompt conversion
    client.converters.convert_prompt = AsyncMock(side_effect=lambda prompt, model_id=None: prompt)

    return client


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    kernel = MagicMock()
    kernel.ctx.start_span = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )
    kernel.agent.agent_id = "test-agent-id"
    kernel.thread.thread_id = "test-thread-id"
    kernel.agent.name = "test-agent"
    kernel.user.user_id = "test-user"
    kernel.user.cr_tenant_id = "test-tenant"
    kernel.prompts.record_tools_in_trace = MagicMock()

    # Create a proper async context manager for langsmith tracing
    class AsyncContextManager:
        async def __aenter__(self):
            return {}

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Use the AsyncContextManager for trace_llm
    kernel.ctx.langsmith.trace_llm = MagicMock(return_value=AsyncContextManager())
    kernel.ctx.langsmith.format_response_for_langsmith = MagicMock(return_value={})

    return kernel


@pytest.mark.asyncio
async def test_generate_response_truncates_tool_results(mock_platform_client, mock_kernel):
    """Test that generate_response truncates large tool results using
    TruncationFinalizer."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Create a large tool result (enough to trigger truncation)
    large_result = "This is a very large tool result. " * 10000  # Lots of tokens

    # Create a prompt with the large tool result
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Get a reference to the original text for comparison
    original_text = prompt.messages[1].content[0].content[0].text  # type: ignore

    # Force the context window to be small to trigger truncation
    mock_platform_client.model_map.model_context_windows["gpt-4"] = 2000

    # Call generate_response
    await platform_interface.generate_response(prompt, "gpt-4")

    # Verify the prompt was passed to the client's generate_response method
    mock_platform_client.generate_response.assert_called_once()

    # Get the finalized prompt that was passed to generate_response
    converted_prompt = mock_platform_client.converters.convert_prompt.call_args[0][0]

    # Verify truncation occurred
    truncated_text = converted_prompt.messages[1].content[0].content[0].text  # type: ignore
    assert len(truncated_text) < len(original_text)
    assert "[Tool result truncated due to length constraints]" in truncated_text


@pytest.mark.asyncio
async def test_stream_response_truncates_tool_results(mock_platform_client, mock_kernel):
    """Test that stream_response truncates large tool results using
    TruncationFinalizer."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Set up the generate_stream_response to return an empty stream
    mock_platform_client.generate_stream_response = MagicMock(
        return_value=AsyncMock(__aiter__=AsyncMock(return_value=iter([])), __anext__=AsyncMock())
    )

    # Create a large tool result (enough to trigger truncation)
    large_result = "This is a very large tool result. " * 10000  # Lots of tokens

    # Create a prompt with the large tool result
    prompt = Prompt(
        messages=[  # type: ignore
            PromptUserMessage([PromptTextContent(text="What's the weather?")]),
            PromptAgentMessage(
                [
                    PromptToolResultContent(  # type: ignore
                        tool_call_id="call_123",
                        tool_name="get_weather",
                        content=[PromptTextContent(text=large_result)],
                    )
                ]
            ),
        ],
    )

    # Get a reference to the original text for comparison
    original_text = prompt.messages[1].content[0].content[0].text  # type: ignore

    # Force the context window to be small to trigger truncation
    mock_platform_client.model_map.model_context_windows["gpt-4"] = 2000

    # Call stream_response
    async with platform_interface.stream_response(prompt, "gpt-4"):
        pass  # We don't need to do anything with the stream

    # Verify the correct prompt was passed to the client's
    # generate_stream_response method
    mock_platform_client.generate_stream_response.assert_called_once()

    # Get the finalized prompt that was passed to generate_stream_response
    converted_prompt = mock_platform_client.converters.convert_prompt.call_args[0][0]

    # Verify truncation occurred
    truncated_text = converted_prompt.messages[1].content[0].content[0].text  # type: ignore
    assert len(truncated_text) < len(original_text)
    assert "[Tool result truncated due to length constraints]" in truncated_text
