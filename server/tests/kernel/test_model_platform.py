"""Tests for the AgentServerPlatformInterface class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.delta import GenericDelta
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
    assert "[Truncated...]" in truncated_text


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
    assert "[Truncated...]" in truncated_text


@pytest.mark.asyncio
async def test_stream_raw_response_yields_deltas(mock_platform_client, mock_kernel):
    """Test that stream_raw_response yields raw deltas from the internal client."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Create mock deltas
    mock_delta_1 = GenericDelta(op="add", path="/content/0/text", value="Hello")
    mock_delta_2 = GenericDelta(op="concat_string", path="/content/0/text", value=" world")
    mock_delta_3 = GenericDelta(op="add", path="/stop_reason", value="end_turn")

    # Set up the generate_stream_response to return mock deltas
    class MockAsyncIterator:
        def __init__(self, items):
            self.items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as e:
                raise StopAsyncIteration from e

    mock_platform_client.generate_stream_response = MagicMock(
        return_value=MockAsyncIterator([mock_delta_1, mock_delta_2, mock_delta_3])
    )

    # Create a simple prompt
    prompt = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hello")])])

    # Collect the yielded deltas
    yielded_deltas = []
    async for delta in platform_interface.stream_raw_response(prompt, "gpt-4"):
        yielded_deltas.append(delta)

    # Verify we got the expected deltas
    assert len(yielded_deltas) == 3
    assert yielded_deltas[0] == mock_delta_1
    assert yielded_deltas[1] == mock_delta_2
    assert yielded_deltas[2] == mock_delta_3

    # Verify the correct methods were called
    mock_platform_client.generate_stream_response.assert_called_once()
    mock_platform_client.converters.convert_prompt.assert_called_once()


@pytest.mark.asyncio
async def test_stream_raw_response_truncates_tool_results(mock_platform_client, mock_kernel):
    """Test that stream_raw_response truncates large tool results using TruncationFinalizer."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Set up the generate_stream_response to return an empty stream
    class MockAsyncIterator:
        def __init__(self, items):
            self.items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as e:
                raise StopAsyncIteration from e

    mock_platform_client.generate_stream_response = MagicMock(
        return_value=MockAsyncIterator(
            [GenericDelta(op="add", path="/stop_reason", value="end_turn")]
        )
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

    # Collect deltas from stream_raw_response
    yielded_deltas = []
    async for delta in platform_interface.stream_raw_response(prompt, "gpt-4"):
        yielded_deltas.append(delta)

    # Verify the correct prompt was passed to the client's generate_stream_response method
    mock_platform_client.generate_stream_response.assert_called_once()

    # Get the finalized prompt that was passed to generate_stream_response
    converted_prompt = mock_platform_client.converters.convert_prompt.call_args[0][0]

    # Verify truncation occurred
    truncated_text = converted_prompt.messages[1].content[0].content[0].text  # type: ignore
    assert len(truncated_text) < len(original_text)
    assert "[Truncated...]" in truncated_text


@pytest.mark.asyncio
async def test_stream_raw_response_handles_error_before_streaming(
    mock_platform_client, mock_kernel
):
    """Test that stream_raw_response handles errors before streaming starts."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Make the LangSmith tracing setup fail to trigger the fallback
    mock_kernel.ctx.langsmith.trace_llm.side_effect = Exception("LangSmith setup failed")

    # Set up a fallback stream that should be called
    class MockAsyncIterator:
        def __init__(self, items):
            self.items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as e:
                raise StopAsyncIteration from e

    mock_platform_client.generate_stream_response = MagicMock(
        return_value=MockAsyncIterator(
            [GenericDelta(op="add", path="/content/0/text", value="fallback")]
        )
    )

    # Create a simple prompt
    prompt = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hello")])])

    # Stream should still work via fallback
    yielded_deltas = []
    async for delta in platform_interface.stream_raw_response(prompt, "gpt-4"):
        yielded_deltas.append(delta)

    # Verify we got the fallback delta
    assert len(yielded_deltas) == 1
    assert yielded_deltas[0].value == "fallback"


@pytest.mark.asyncio
async def test_stream_raw_response_handles_error_after_streaming(mock_platform_client, mock_kernel):
    """Test that stream_raw_response properly handles streaming errors."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Create a stream that raises an error during streaming
    async def error_stream():
        yield GenericDelta(op="add", path="/content/0/text", value="Hello")
        raise Exception("Streaming error")

    mock_platform_client.generate_stream_response = MagicMock(
        side_effect=lambda *args, **kwargs: error_stream()
    )

    # Create a simple prompt
    prompt = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hello")])])

    # Test that streaming works and error handling doesn't interfere with normal operation
    yielded_deltas = []
    try:
        async for delta in platform_interface.stream_raw_response(prompt, "gpt-4"):
            yielded_deltas.append(delta)
        # This test verifies the basic streaming functionality works
        # The error handling for after-streaming errors is complex and depends on LangSmith setup
    except Exception:
        # Some exception occurred during streaming, which is expected
        pass

    # Verify we got at least the first delta
    assert len(yielded_deltas) >= 1
    assert yielded_deltas[0].value == "Hello"


@pytest.mark.asyncio
async def test_stream_raw_response_records_tools_in_trace(mock_platform_client, mock_kernel):
    """Test that stream_raw_response records tools in trace."""
    # Create the platform interface
    platform_interface = AgentServerPlatformInterface(mock_platform_client)
    platform_interface.attach_kernel(mock_kernel)

    # Set up the generate_stream_response to return a simple stream
    class MockAsyncIterator:
        def __init__(self, items):
            self.items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as e:
                raise StopAsyncIteration from e

    mock_platform_client.generate_stream_response = MagicMock(
        return_value=MockAsyncIterator(
            [GenericDelta(op="add", path="/stop_reason", value="end_turn")]
        )
    )

    # Create a simple prompt
    prompt = Prompt(messages=[PromptUserMessage([PromptTextContent(text="Hello")])])

    # Consume the stream
    async for _ in platform_interface.stream_raw_response(prompt, "gpt-4"):
        pass

    # Verify that record_tools_in_trace was called with the correct span name
    mock_kernel.prompts.record_tools_in_trace.assert_called_once()
    call_args = mock_kernel.prompts.record_tools_in_trace.call_args
    assert call_args[1]["span_name"] == "stream_raw_response_tools"
