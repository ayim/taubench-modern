"""Tests for the AgentServerToolsInterface class."""

import asyncio
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent_platform.core.actions.action_utils import ActionResponse
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition
from agent_platform.server.kernel.tools import AgentServerToolsInterface


@pytest.fixture
def mock_kernel():
    """Create a mock kernel for testing."""
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    kernel = MagicMock()
    kernel.ctx.start_span = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
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

    kernel.data_frames = AgentServerDataFramesInterface()
    kernel.data_frames.attach_kernel(kernel)

    return kernel


@pytest.fixture
def tools_interface(mock_kernel):
    """Create a tools interface for testing."""
    interface = AgentServerToolsInterface()
    interface.attach_kernel(mock_kernel)
    return interface


@pytest.mark.asyncio
async def test_internal_error_handling(tools_interface: AgentServerToolsInterface):
    """Test that internal errors from tools are properly handled."""

    # Create a tool that returns an internal error
    async def internal_error_tool(**kwargs):
        return {"error_code": "internal-error", "message": "test exception!"}

    tool_def = ToolDefinition(
        name="error_tool",
        description="A tool that returns an internal error",
        input_schema={"type": "object", "properties": {}},
        function=internal_error_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="error_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error == "internal-error: test exception!"
    assert result.output_raw == {
        "error_code": "internal-error",
        "message": "test exception!",
    }
    assert result.definition == tool_def
    assert result.tool_call_id == "call_123"


@pytest.mark.asyncio
async def test_result_with_error_handling(tools_interface: AgentServerToolsInterface):
    """Test that errors in the result/error format are properly handled."""

    # Create a tool that returns {"result": None, "error": "error-message"} format
    async def result_error_tool(**kwargs):
        return {"result": None, "error": "Something went wrong with the API"}

    tool_def = ToolDefinition(
        name="result_error_tool",
        description="A tool that returns result/error format",
        input_schema={"type": "object", "properties": {}},
        function=result_error_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_789",
        tool_name="result_error_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error == "Something went wrong with the API"
    assert result.output_raw == {
        "result": None,
        "error": "Something went wrong with the API",
    }
    assert result.definition == tool_def
    assert result.tool_call_id == "call_789"


@pytest.mark.asyncio
async def test_action_response_inline_error_result_error_pattern(
    tools_interface: AgentServerToolsInterface,
):
    """ActionResponse with {"result": None, "error": "..."} should elevate error."""

    async def tool_func(**kwargs):
        return ActionResponse(result=None, error="Boom")

    tool_def = ToolDefinition(
        name="action_response_error_result_pattern",
        description="Tool returns ActionResponse with inline error in result/error pattern",
        input_schema={"type": "object", "properties": {}},
        function=tool_func,
    )

    tool_use = ResponseToolUseContent(
        tool_call_id="call_ar_err_pattern",
        tool_name="action_response_error_result_pattern",
        tool_input_raw="{}",
    )

    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    assert result.error == "Boom"
    assert result.output_raw is None
    assert result.tool_call_id == "call_ar_err_pattern"


@pytest.mark.asyncio
async def test_async_action_timeout_error_message(
    tools_interface: AgentServerToolsInterface,
):
    """Ensure ReadTimeout exceptions surface a non-empty error message."""

    async def timeout_tool(**kwargs):
        raise httpx.ReadTimeout("")

    tool_def = ToolDefinition(
        name="timeout_tool",
        description="A tool that raises a ReadTimeout",
        input_schema={"type": "object", "properties": {}},
        function=timeout_tool,
    )

    tool_use = ResponseToolUseContent(
        tool_call_id="call_timeout",
        tool_name="timeout_tool",
        tool_input_raw="{}",
    )

    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    assert result.error
    assert "ReadTimeout" in result.error
    assert result.output_raw is None


@pytest.mark.asyncio
async def test_validation_error_handling(tools_interface: AgentServerToolsInterface):
    """Test that validation errors from tools are properly handled."""

    # Create a tool that returns a validation error
    async def validation_error_tool(**kwargs):
        return {
            "error_code": "validation-error",
            "message": (
                "The received input arguments (sent in the body) do not conform to the "
                "expected API. Details: 'search_term' is a required property\n\n"
                "Failed validating 'required' in schema:\n"
                "    {'properties': {'search_term': {'type': 'string',\n"
                "                                    'description': "
                "'A search term for the '\n"
                "                                                   "
                "'Youtube video search, '\n"
                "                                                   "
                "'example: \"Agentic '\n"
                "                                                   "
                "'Automation\"',\n"
                "                                    'title': 'Search Term'},\n"
                "                    'max_results': {'type': 'integer',\n"
                "                                    'description': "
                "'How many results to '\n"
                "                                                   "
                "'return, default 3.',\n"
                "                                    'title': 'Max Results',\n"
                "                                    'default': 3}},\n"
                "     'type': 'object',\n"
                "     'required': ['search_term']}\n\n"
                "On instance:\n"
                "    {}"
            ),
        }

    tool_def = ToolDefinition(
        name="validation_error_tool",
        description="A tool that returns a validation error",
        input_schema={"type": "object", "properties": {}},
        function=validation_error_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_456",
        tool_name="validation_error_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error is not None
    assert result.error.startswith("validation-error: The received input arguments")
    assert result.output_raw is not None
    assert result.output_raw["error_code"] == "validation-error"
    assert result.definition == tool_def
    assert result.tool_call_id == "call_456"


@pytest.mark.asyncio
async def test_error_in_execute_pending_tool_calls(tools_interface: AgentServerToolsInterface):
    """Test that errors are properly handled in execute_pending_tool_calls."""

    # Create a tool that returns an error
    async def error_tool(**kwargs):
        return {"error_code": "test-error", "message": "Test error message"}

    tool_def = ToolDefinition(
        name="error_tool",
        description="A tool that returns an error",
        input_schema={"type": "object", "properties": {}},
        function=error_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_789",
        tool_name="error_tool",
        tool_input_raw="{}",
    )

    # Execute pending tool calls
    pending_calls = [(tool_def, tool_use)]
    results = []

    async for result in tools_interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Verify the error is properly handled
    assert len(results) == 1
    assert results[0].error == "test-error: Test error message"
    assert results[0].output_raw == {
        "error_code": "test-error",
        "message": "Test error message",
    }


@pytest.mark.asyncio
async def test_malformed_json_handling(tools_interface: AgentServerToolsInterface):
    """Test that malformed JSON in tool input is properly handled."""

    # Create a simple tool function
    async def sample_tool(**kwargs):
        return {"result": "success"}

    tool_def = ToolDefinition(
        name="sample_tool",
        description="A sample tool",
        input_schema={"type": "object", "properties": {}},
        function=sample_tool,
    )

    # Patch the ToolExecutionResult.__post_init__ method to handle invalid JSON
    with patch("agent_platform.core.tools.tool_execution_result.ToolExecutionResult.__post_init__") as mock_post_init:
        # Make post_init do nothing (skip JSON parsing)
        mock_post_init.return_value = None

        # Create a tool use request with malformed JSON
        tool_use = MagicMock(spec=ResponseToolUseContent)
        tool_use.tool_call_id = "call_invalid"
        tool_use.tool_name = "sample_tool"
        tool_use.tool_input_raw = "{invalid json"

        # Execute the tool with our mocked request
        result = await tools_interface._safe_execute_tool(tool_def, tool_use)

        # Verify the error is properly handled
        assert result.error is not None
        assert "Expecting property name" in result.error or "Unterminated string" in result.error
        assert result.output_raw is None

        # Verify our mock was called
        mock_post_init.assert_called()


@pytest.mark.asyncio
async def test_tool_exception_handling(tools_interface: AgentServerToolsInterface):
    """Test that exceptions during tool execution are properly handled."""

    # Create a tool that raises an exception
    async def exception_tool(**kwargs):
        raise ValueError("Unexpected error during execution")

    tool_def = ToolDefinition(
        name="exception_tool",
        description="A tool that raises an exception",
        input_schema={"type": "object", "properties": {}},
        function=exception_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_exception",
        tool_name="exception_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify the exception is properly handled
    assert result.error == "Unexpected error during execution"
    assert result.output_raw is None


@pytest.mark.asyncio
async def test_none_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that None results from tools are properly handled."""

    # Create a tool that returns None
    async def none_tool(**kwargs):
        return None

    tool_def = ToolDefinition(
        name="none_tool",
        description="A tool that returns None",
        input_schema={"type": "object", "properties": {}},
        function=none_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_none",
        tool_name="none_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify None is properly handled
    assert result.error is None
    assert result.output_raw is None
    assert result.definition == tool_def
    assert result.tool_call_id == "call_none"


@pytest.mark.asyncio
async def test_string_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that string results from tools are properly handled."""

    # Create a tool that returns a string
    async def string_tool(**kwargs):
        return "Hello, world!"

    tool_def = ToolDefinition(
        name="string_tool",
        description="A tool that returns a string",
        input_schema={"type": "object", "properties": {}},
        function=string_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_string",
        tool_name="string_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify string is properly handled
    assert result.error is None
    assert result.output_raw == "Hello, world!"
    assert result.definition == tool_def
    assert result.tool_call_id == "call_string"


@pytest.mark.asyncio
async def test_integer_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that integer results from tools are properly handled."""

    # Create a tool that returns an integer
    async def integer_tool(**kwargs):
        return 42

    tool_def = ToolDefinition(
        name="integer_tool",
        description="A tool that returns an integer",
        input_schema={"type": "object", "properties": {}},
        function=integer_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_integer",
        tool_name="integer_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify integer is properly handled
    assert result.error is None
    assert result.output_raw == 42
    assert result.definition == tool_def
    assert result.tool_call_id == "call_integer"


@pytest.mark.asyncio
async def test_float_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that float results from tools are properly handled."""

    # Create a tool that returns a float
    async def float_tool(**kwargs):
        return 3.14159

    tool_def = ToolDefinition(
        name="float_tool",
        description="A tool that returns a float",
        input_schema={"type": "object", "properties": {}},
        function=float_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_float",
        tool_name="float_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify float is properly handled
    assert result.error is None
    assert result.output_raw == 3.14159
    assert result.definition == tool_def
    assert result.tool_call_id == "call_float"


@pytest.mark.asyncio
async def test_boolean_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that boolean results from tools are properly handled."""

    # Test both True and False values
    test_cases = [
        ("true_tool", True),
        ("false_tool", False),
    ]

    for tool_name, bool_value in test_cases:
        # Create a tool that returns a boolean
        async def boolean_tool(value=bool_value, **kwargs):
            return value

        tool_def = ToolDefinition(
            name=tool_name,
            description=f"A tool that returns {bool_value}",
            input_schema={"type": "object", "properties": {}},
            function=boolean_tool,
        )

        # Create a tool use request
        tool_use = ResponseToolUseContent(
            tool_call_id=f"call_{tool_name}",
            tool_name=tool_name,
            tool_input_raw="{}",
        )

        # Execute the tool
        result = await tools_interface._safe_execute_tool(tool_def, tool_use)

        # Verify boolean is properly handled
        assert result.error is None
        assert result.output_raw == bool_value
        assert result.definition == tool_def
        assert result.tool_call_id == f"call_{tool_name}"


@pytest.mark.asyncio
async def test_malformed_result_handling(tools_interface: AgentServerToolsInterface):
    """Test that malformed (non-primitive, non-dict) results are properly handled."""

    # Create a tool that returns a malformed result (e.g., a list)
    async def malformed_tool(**kwargs):
        return ["this", "is", "a", "list"]

    tool_def = ToolDefinition(
        name="malformed_tool",
        description="A tool that returns a malformed result",
        input_schema={"type": "object", "properties": {}},
        function=malformed_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_malformed",
        tool_name="malformed_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify malformed result is properly handled
    assert result.error == "Received a malformed result from the tool"
    assert result.output_raw == ["this", "is", "a", "list"]
    assert result.definition == tool_def
    assert result.tool_call_id == "call_malformed"


@pytest.mark.asyncio
async def test_dict_with_empty_error_code_handling(tools_interface: AgentServerToolsInterface):
    """Test that dict results with empty error_code are treated as successful."""

    # Create a tool that returns a dict with empty error_code
    async def success_dict_tool(**kwargs):
        return {"error_code": "", "data": "success", "count": 5}

    tool_def = ToolDefinition(
        name="success_dict_tool",
        description="A tool that returns a dict with empty error_code",
        input_schema={"type": "object", "properties": {}},
        function=success_dict_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_success_dict",
        tool_name="success_dict_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify dict with empty error_code is treated as successful
    assert result.error is None
    assert result.output_raw == {"error_code": "", "data": "success", "count": 5}
    assert result.definition == tool_def
    assert result.tool_call_id == "call_success_dict"


@pytest.mark.asyncio
async def test_dict_without_error_code_handling(tools_interface: AgentServerToolsInterface):
    """Test that dict results without error_code are treated as successful."""

    # Create a tool that returns a dict without error_code
    async def normal_dict_tool(**kwargs):
        return {"result": "success", "data": {"key": "value"}, "status": "ok"}

    tool_def = ToolDefinition(
        name="normal_dict_tool",
        description="A tool that returns a normal dict",
        input_schema={"type": "object", "properties": {}},
        function=normal_dict_tool,
    )

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_normal_dict",
        tool_name="normal_dict_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await tools_interface._safe_execute_tool(tool_def, tool_use)

    # Verify dict without error_code is treated as successful
    assert result.error is None
    assert result.output_raw == {
        "result": "success",
        "data": {"key": "value"},
        "status": "ok",
    }
    assert result.definition == tool_def
    assert result.tool_call_id == "call_normal_dict"


@pytest.mark.asyncio
async def test_client_exec_tool_success(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that client-exec-tool properly waits for and processes client results."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    from agent_platform.core.streaming.delta import StreamingDeltaRequestToolExecution
    from agent_platform.core.streaming.incoming import IncomingDeltaClientToolResult

    # Create a client-exec-tool definition
    tool_def = ToolDefinition(
        name="client_exec_tool",
        description="A tool that executes on the client side",
        input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
        category="client-exec-tool",
    )

    # Create the tools interface with mocked kernel
    mock_kernel.agent.agent_id = "test-agent"
    mock_kernel.thread.thread_id = "test-thread"
    mock_kernel.user.cr_user_id = "test-user"

    # Mock the outgoing events dispatcher
    mock_kernel.outgoing_events.dispatch = AsyncMock()

    # Mock the incoming events to simulate client response
    mock_client_result = IncomingDeltaClientToolResult(
        timestamp=datetime.now(UTC),
        tool_call_id="call_123",
        result={"output": "Command executed successfully", "error": None},
    )

    mock_kernel.incoming_events.wait_for_event = AsyncMock(return_value=asdict(mock_client_result))

    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="client_exec_tool",
        tool_input_raw='{"command": "ls -la"}',
    )

    # Execute the client tool
    result = await tools_interface._safe_execute_client_tool(tool_def, tool_use)

    # Verify the outgoing event was dispatched correctly
    mock_kernel.outgoing_events.dispatch.assert_called_once()
    dispatched_event = mock_kernel.outgoing_events.dispatch.call_args[0][0]
    assert isinstance(dispatched_event, StreamingDeltaRequestToolExecution)
    assert dispatched_event.tool_name == "client_exec_tool"
    assert dispatched_event.tool_call_id == "call_123"
    assert dispatched_event.input_raw == '{"command": "ls -la"}'
    assert dispatched_event.requires_execution is True

    # Verify the incoming event was waited for correctly
    mock_kernel.incoming_events.wait_for_event.assert_called_once()
    wait_predicate = mock_kernel.incoming_events.wait_for_event.call_args[0][0]

    # Test the predicate function
    assert wait_predicate(asdict(mock_client_result)) is True

    # Test predicate with wrong tool_call_id
    wrong_result = IncomingDeltaClientToolResult(
        timestamp=datetime.now(UTC),
        tool_call_id="wrong_id",
        result={"output": "test", "error": None},
    )
    assert wait_predicate(asdict(wrong_result)) is False

    # Verify the result
    assert result.error is None
    assert result.output_raw == "Command executed successfully"
    assert result.definition == tool_def
    assert result.tool_call_id == "call_123"


@pytest.mark.asyncio
async def test_client_exec_tool_with_error(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that client-exec-tool properly handles errors from client."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    from agent_platform.core.streaming.incoming import IncomingDeltaClientToolResult

    # Create a client-exec-tool definition
    tool_def = ToolDefinition(
        name="client_exec_tool",
        description="A tool that executes on the client side",
        input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
        category="client-exec-tool",
    )

    mock_kernel.outgoing_events.dispatch = AsyncMock()

    # Mock client returning an error
    mock_client_result = IncomingDeltaClientToolResult(
        timestamp=datetime.now(UTC),
        tool_call_id="call_456",
        result={"output": None, "error": "Command failed: permission denied"},
    )

    mock_kernel.incoming_events.wait_for_event = AsyncMock(return_value=asdict(mock_client_result))

    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_456",
        tool_name="client_exec_tool",
        tool_input_raw='{"command": "rm -rf /"}',
    )

    # Execute the client tool
    result = await tools_interface._safe_execute_client_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error == "Command failed: permission denied"
    assert result.output_raw is None
    assert result.definition == tool_def
    assert result.tool_call_id == "call_456"


@pytest.mark.asyncio
async def test_client_exec_tool_cancellation(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that client-exec-tool properly handles cancellation/disconnection."""
    from unittest.mock import AsyncMock

    # Create a client-exec-tool definition
    tool_def = ToolDefinition(
        name="client_exec_tool",
        description="A tool that executes on the client side",
        input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
        category="client-exec-tool",
    )

    mock_kernel.outgoing_events.dispatch = AsyncMock()

    # Mock incoming events to raise CancelledError (simulating client disconnect)
    mock_kernel.incoming_events.wait_for_event = AsyncMock(side_effect=asyncio.CancelledError("Client disconnected"))

    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_789",
        tool_name="client_exec_tool",
        tool_input_raw='{"command": "long_running_command"}',
    )

    # Execute the client tool
    result = await tools_interface._safe_execute_client_tool(tool_def, tool_use)

    # Verify the cancellation is properly handled
    assert result.error == "Tool execution cancelled due to client disconnection"
    assert result.output_raw is None
    assert result.definition == tool_def
    assert result.tool_call_id == "call_789"


@pytest.mark.asyncio
async def test_client_info_tool(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that client-info-tool dispatches event but doesn't wait for execution."""
    from unittest.mock import AsyncMock

    from agent_platform.core.streaming.delta import StreamingDeltaRequestToolExecution

    # Create a client-info-tool definition
    tool_def = ToolDefinition(
        name="client_info_tool",
        description="A tool that provides info to the client without execution",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        category="client-info-tool",
    )

    # Mock the outgoing events dispatcher
    mock_kernel.outgoing_events.dispatch = AsyncMock()

    # We should NOT mock incoming_events.wait_for_event since it shouldn't be called
    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="info_123",
        tool_name="client_info_tool",
        tool_input_raw='{"message": "Display this information"}',
    )

    # Execute the client tool
    result = await tools_interface._safe_execute_client_tool(tool_def, tool_use)

    # Verify the outgoing event was dispatched correctly
    mock_kernel.outgoing_events.dispatch.assert_called_once()
    dispatched_event = mock_kernel.outgoing_events.dispatch.call_args[0][0]
    assert isinstance(dispatched_event, StreamingDeltaRequestToolExecution)
    assert dispatched_event.tool_name == "client_info_tool"
    assert dispatched_event.tool_call_id == "info_123"
    assert dispatched_event.input_raw == '{"message": "Display this information"}'
    assert dispatched_event.requires_execution is False

    # Verify the result (should complete immediately with empty output)
    assert result.error is None
    assert result.output_raw == {}
    assert result.definition == tool_def
    assert result.tool_call_id == "info_123"


@pytest.mark.asyncio
async def test_execute_pending_tool_calls_with_client_tools(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that execute_pending_tool_calls properly handles client tools."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    from agent_platform.core.streaming.incoming import IncomingDeltaClientToolResult

    # Create mixed tool definitions
    client_exec_tool = ToolDefinition(
        name="client_exec_tool",
        description="Execute on client",
        input_schema={"type": "object"},
        category="client-exec-tool",
    )

    client_info_tool = ToolDefinition(
        name="client_info_tool",
        description="Info for client",
        input_schema={"type": "object"},
        category="client-info-tool",
    )

    mock_kernel.outgoing_events.dispatch = AsyncMock()

    # Mock client response only for exec tool
    mock_client_result = IncomingDeltaClientToolResult(
        timestamp=datetime.now(UTC),
        tool_call_id="exec_call",
        result={"output": "Executed successfully", "error": None},
    )

    mock_kernel.incoming_events.wait_for_event = AsyncMock(return_value=asdict(mock_client_result))

    tools_interface.attach_kernel(mock_kernel)

    # Create tool use requests
    exec_tool_use = ResponseToolUseContent(
        tool_call_id="exec_call",
        tool_name="client_exec_tool",
        tool_input_raw='{"action": "run"}',
    )

    info_tool_use = ResponseToolUseContent(
        tool_call_id="info_call",
        tool_name="client_info_tool",
        tool_input_raw='{"message": "show info"}',
    )

    # Create pending tool calls
    pending_calls = [
        (client_exec_tool, exec_tool_use),
        (client_info_tool, info_tool_use),
    ]

    # Execute the tools
    results = []
    async for result in tools_interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Should have 2 results
    assert len(results) == 2

    # Find results by tool call id
    exec_result = next(r for r in results if r.tool_call_id == "exec_call")
    info_result = next(r for r in results if r.tool_call_id == "info_call")

    # Verify exec tool result
    assert exec_result.error is None
    assert exec_result.output_raw == "Executed successfully"
    assert exec_result.definition.name == "client_exec_tool"

    # Verify info tool result
    assert info_result.error is None
    assert info_result.output_raw == {}
    assert info_result.definition.name == "client_info_tool"

    # Verify correct number of outgoing events dispatched
    assert mock_kernel.outgoing_events.dispatch.call_count == 2

    # Verify wait_for_event was called only once (for exec tool)
    mock_kernel.incoming_events.wait_for_event.assert_called_once()


@pytest.mark.asyncio
async def test_client_tool_categories_in_execute_pending_tool_calls(
    tools_interface: AgentServerToolsInterface, mock_kernel
):
    """Test that the tool category routing works correctly in execute_pending_tool_calls."""
    from unittest.mock import AsyncMock

    # Create tools of different categories
    action_tool = ToolDefinition(
        name="action_tool",
        description="Server action tool",
        input_schema={"type": "object"},
        function=lambda: "action result",
        category="action-tool",
    )

    mcp_tool = ToolDefinition(
        name="mcp_tool",
        description="MCP tool",
        input_schema={"type": "object"},
        category="mcp-tool",
    )

    client_exec_tool = ToolDefinition(
        name="client_exec_tool",
        description="Client exec tool",
        input_schema={"type": "object"},
        category="client-exec-tool",
    )

    client_info_tool = ToolDefinition(
        name="client_info_tool",
        description="Client info tool",
        input_schema={"type": "object"},
        category="client-info-tool",
    )

    mock_kernel.outgoing_events.dispatch = AsyncMock()

    tools_interface.attach_kernel(mock_kernel)

    # Create tool use requests
    tool_uses = [
        ResponseToolUseContent(
            tool_call_id="action_call",
            tool_name="action_tool",
            tool_input_raw="{}",
        ),
        ResponseToolUseContent(
            tool_call_id="mcp_call",
            tool_name="mcp_tool",
            tool_input_raw="{}",
        ),
        ResponseToolUseContent(
            tool_call_id="exec_call",
            tool_name="client_exec_tool",
            tool_input_raw="{}",
        ),
        ResponseToolUseContent(
            tool_call_id="info_call",
            tool_name="client_info_tool",
            tool_input_raw="{}",
        ),
    ]

    pending_calls = [
        (action_tool, tool_uses[0]),
        (mcp_tool, tool_uses[1]),
        (client_exec_tool, tool_uses[2]),
        (client_info_tool, tool_uses[3]),
    ]

    # Mock the specific execution methods to track which ones are called
    with (
        patch.object(tools_interface, "_safe_execute_tool", new_callable=AsyncMock) as mock_execute_tool,
        patch.object(tools_interface, "_safe_execute_client_tool", new_callable=AsyncMock) as mock_execute_client_tool,
    ):
        # Mock return values
        mock_execute_tool.return_value = MagicMock(tool_call_id="action_call")
        mock_execute_client_tool.return_value = MagicMock(tool_call_id="client_call")

        # Execute the tools (we'll get an error due to mocking, but we can verify the routing)
        results = []
        try:
            async for result in tools_interface.execute_pending_tool_calls(pending_calls):
                results.append(result)
        except Exception:
            # Expected due to mocking, but we can still check the calls
            pass

        # Verify _safe_execute_tool was called twice for action-tool and mcp-tool
        assert mock_execute_tool.call_count == 2
        non_client_call_names = {call[0][0].name for call in mock_execute_tool.call_args_list}
        assert "action_tool" in non_client_call_names
        assert "mcp_tool" in non_client_call_names

        non_client_tool_ids = {call[0][1].tool_call_id for call in mock_execute_tool.call_args_list}
        assert "action_call" in non_client_tool_ids
        assert "mcp_call" in non_client_tool_ids

        # Verify _safe_execute_client_tool was called twice for client tools
        assert mock_execute_client_tool.call_count == 2
        client_calls = mock_execute_client_tool.call_args_list

        # Check that both client tools were routed correctly
        client_tool_names = {call[0][0].name for call in client_calls}
        assert "client_exec_tool" in client_tool_names
        assert "client_info_tool" in client_tool_names

        client_tool_ids = {call[0][1].tool_call_id for call in client_calls}
        assert "exec_call" in client_tool_ids
        assert "info_call" in client_tool_ids


@pytest.mark.asyncio
async def test_tool_call_headers_with_user_id(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that tool call headers include user ID when available."""
    from unittest.mock import AsyncMock

    captured_headers = {}

    # Create a tool that captures the extra_headers parameter
    async def header_capture_tool(extra_headers=None, **kwargs):
        nonlocal captured_headers
        captured_headers = extra_headers or {}
        return {"result": "success"}

    tool_def = ToolDefinition(
        name="header_capture_tool",
        description="A tool that captures headers",
        input_schema={"type": "object", "properties": {}},
        function=header_capture_tool,
    )

    # Create the tools interface with mocked kernel
    mock_kernel.outgoing_events.dispatch = AsyncMock()
    mock_kernel.user.cr_user_id = "test-user-id"
    mock_kernel.user.cr_system_id = "test-system-id"

    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="header_capture_tool",
        tool_input_raw="{}",
    )

    # Execute pending tool calls
    pending_calls = [(tool_def, tool_use)]
    results = []

    async for result in tools_interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Verify headers were passed correctly
    assert len(results) == 1
    assert results[0].error is None
    assert results[0].output_raw == {"result": "success"}

    # Verify the headers include user ID (not system ID) when user ID is available
    assert "x-invoked_by_assistant_id" in captured_headers
    assert captured_headers["x-invoked_by_assistant_id"] == "test-agent-id"
    assert "x-invoked_on_behalf_of_user_id" in captured_headers
    assert captured_headers["x-invoked_on_behalf_of_user_id"] == "test-user-id"
    assert "x-invoked_for_thread_id" in captured_headers
    assert captured_headers["x-invoked_for_thread_id"] == "test-thread-id"
    assert "x-action_invocation_id" in captured_headers
    assert captured_headers["x-action_invocation_id"] == "call_123"


@pytest.mark.asyncio
async def test_tool_call_headers_with_system_id_fallback(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that tool call headers use system ID when user ID is empty."""
    captured_headers = {}

    # Create a tool that captures the extra_headers parameter
    async def header_capture_tool(extra_headers=None, **kwargs):
        nonlocal captured_headers
        captured_headers = extra_headers or {}
        return {"result": "success"}

    tool_def = ToolDefinition(
        name="header_capture_tool",
        description="A tool that captures headers",
        input_schema={"type": "object", "properties": {}},
        function=header_capture_tool,
    )

    # Create the tools interface with mocked kernel
    mock_kernel.agent.agent_id = "test-agent-id"
    mock_kernel.thread.thread_id = "test-thread-id"
    mock_kernel.user.cr_user_id = None  # No user ID - should use system ID
    mock_kernel.user.cr_system_id = "test-system-id"

    tools_interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_456",
        tool_name="header_capture_tool",
        tool_input_raw="{}",
    )

    # Execute pending tool calls
    pending_calls = [(tool_def, tool_use)]
    results = []

    async for result in tools_interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Verify headers were passed correctly
    assert len(results) == 1
    assert results[0].error is None
    assert results[0].output_raw == {"result": "success"}

    # Verify the headers use system ID when user ID is None
    assert "x-invoked_by_assistant_id" in captured_headers
    assert captured_headers["x-invoked_by_assistant_id"] == "test-agent-id"
    assert "x-invoked_on_behalf_of_user_id" in captured_headers
    assert captured_headers["x-invoked_on_behalf_of_user_id"] == "test-system-id"
    assert "x-invoked_for_thread_id" in captured_headers
    assert captured_headers["x-invoked_for_thread_id"] == "test-thread-id"
    assert "x-action_invocation_id" in captured_headers
    assert captured_headers["x-action_invocation_id"] == "call_456"


@pytest.mark.asyncio
async def test_tool_call_headers_with_empty_string_user_id(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that tool call headers use system ID when user ID is empty string."""
    captured_headers = {}

    # Create a tool that captures the extra_headers parameter
    async def header_capture_tool(extra_headers=None, **kwargs):
        nonlocal captured_headers
        captured_headers = extra_headers or {}
        return {"result": "success"}

    tool_def = ToolDefinition(
        name="header_capture_tool",
        description="A tool that captures headers",
        input_schema={"type": "object", "properties": {}},
        function=header_capture_tool,
    )

    # Create the tools interface with mocked kernel
    mock_kernel.agent.agent_id = "test-agent-id"
    mock_kernel.thread.thread_id = "test-thread-id"
    mock_kernel.user.cr_user_id = ""  # Empty string user ID - should use system ID
    mock_kernel.user.cr_system_id = "test-system-id"

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_789",
        tool_name="header_capture_tool",
        tool_input_raw="{}",
    )

    # Execute pending tool calls
    pending_calls = [(tool_def, tool_use)]
    results = []

    async for result in tools_interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Verify headers were passed correctly
    assert len(results) == 1
    assert results[0].error is None
    assert results[0].output_raw == {"result": "success"}

    # Verify the headers use system ID when user ID is empty string
    assert "x-invoked_by_assistant_id" in captured_headers
    assert captured_headers["x-invoked_by_assistant_id"] == "test-agent-id"
    assert "x-invoked_on_behalf_of_user_id" in captured_headers
    assert captured_headers["x-invoked_on_behalf_of_user_id"] == "test-system-id"
    assert "x-invoked_for_thread_id" in captured_headers
    assert captured_headers["x-invoked_for_thread_id"] == "test-thread-id"
    assert "x-action_invocation_id" in captured_headers
    assert captured_headers["x-action_invocation_id"] == "call_789"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "structured_content",
        "content",
        "structured_content_with_error",
        "unexpected_mcp_format",
        "content_with_error",
    ],
)
async def test_mcp_tool_no_runtime_headers(tools_interface: AgentServerToolsInterface, mock_kernel, scenario):
    """Test that internal-tool category tools do not receive extra_headers."""
    function_called_with = {}

    # Create a "fake" MCP type tool
    async def mcp_tool_function(**kwargs):
        nonlocal function_called_with
        function_called_with = kwargs
        if scenario == "structured_content":
            return {"structuredContent": {"result": "mcp tool success"}}

        elif scenario == "content":
            return {"content": "mcp tool success"}

        elif scenario == "content_with_error":
            return {"content": "mcp tool error", "isError": True}

        elif scenario == "structured_content_with_error":
            return {"structuredContent": {"error": "mcp tool error"}}

        elif scenario == "unexpected_mcp_format":
            return {"result": "mcp tool success"}
        else:
            raise ValueError(f"Invalid scenario: {scenario}")

    tool_def = ToolDefinition(
        name="mcp_tool",
        description="An MCP tool that should not receive headers",
        input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
        function=mcp_tool_function,
        category="mcp-tool",
    )

    # Create a tool use request with some parameters
    tool_use = ResponseToolUseContent(
        tool_call_id="mcp_call",
        tool_name="mcp_tool",
        tool_input_raw='{"param": "test_value"}',
    )

    # Execute the tool directly with extra_headers
    extra_headers = {
        "x-test-header": "test-value",
        "x-another-header": "another-value",
    }

    result = await tools_interface._safe_execute_tool(tool_def, tool_use, extra_headers=extra_headers)

    # Verify the tool was called successfully
    if scenario == "structured_content":
        assert result.error is None
        assert result.output_raw == {"result": "mcp tool success"}

    elif scenario == "structured_content_with_error":
        assert result.error == "mcp tool error"

    elif scenario == "content":
        assert result.error is None
        assert result.output_raw == "mcp tool success"

    elif scenario == "content_with_error":
        assert result.error == '"mcp tool error"'

    elif scenario == "unexpected_mcp_format":
        assert result.error is None
        assert result.output_raw == {"result": "mcp tool success"}

    else:
        raise ValueError(f"Invalid scenario: {scenario}")

    assert result.definition == tool_def
    assert result.tool_call_id == "mcp_call"

    # Verify that the function was called with ONLY the JSON args, no extra_headers
    assert function_called_with == {"param": "test_value"}
    assert "extra_headers" not in function_called_with


@pytest.mark.asyncio
async def test_internal_tool_no_headers(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that internal-tool category tools do not receive extra_headers."""
    function_called_with = {}

    # Create a tool that captures its call arguments
    async def internal_tool_function(**kwargs):
        nonlocal function_called_with
        function_called_with = kwargs
        return {"result": "internal tool success"}

    tool_def = ToolDefinition(
        name="internal_tool",
        description="An internal tool that should not receive headers",
        input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
        function=internal_tool_function,
        category="internal-tool",
    )

    # Create a tool use request with some parameters
    tool_use = ResponseToolUseContent(
        tool_call_id="internal_call",
        tool_name="internal_tool",
        tool_input_raw='{"param": "test_value"}',
    )

    # Execute the tool directly with extra_headers
    extra_headers = {
        "x-test-header": "test-value",
        "x-another-header": "another-value",
    }

    result = await tools_interface._safe_execute_tool(tool_def, tool_use, extra_headers=extra_headers)

    # Verify the tool was called successfully
    assert result.error is None
    assert result.output_raw == {"result": "internal tool success"}
    assert result.definition == tool_def
    assert result.tool_call_id == "internal_call"

    # Verify that the function was called with ONLY the JSON args, no extra_headers
    assert function_called_with == {"param": "test_value"}
    assert "extra_headers" not in function_called_with


@pytest.mark.asyncio
async def test_mcp_tools_with_null_selected_tools(tools_interface: AgentServerToolsInterface, mock_kernel):
    """Test that MCP tool filtering works when selected_tools is None (legacy agents)."""
    from agent_platform.core.mcp import MCPServer
    from agent_platform.core.tools.collected_tools import CollectedTools

    # Set selected_tools to None to simulate legacy agents
    mock_kernel.agent.selected_tools = None

    # Create mock MCP tools
    mock_tools = [
        ToolDefinition(
            name="test_tool_1",
            description="Test tool 1",
            input_schema={"type": "object", "properties": {}},
            function=lambda: "result1",
        ),
        ToolDefinition(
            name="test_tool_2",
            description="Test tool 2",
            input_schema={"type": "object", "properties": {}},
            function=lambda: "result2",
        ),
    ]

    # Mock the MCP server tools fetching
    with patch.object(
        tools_interface,
        "_fetch_mcp_tools",
        return_value=CollectedTools(tools=mock_tools, issues=[]),
    ):
        # Create a mock MCP server
        mcp_server = MCPServer(
            name="test_server",
            url="http://test.com",
            transport="streamable-http",
        )

        # Call from_mcp_servers - this should not raise AttributeError
        mcp_result = await tools_interface.from_mcp_servers([mcp_server])
        tools = mcp_result.tools
        issues = mcp_result.issues

        # Verify that all tools are returned (no filtering applied when selected_tools is None)
        assert len(tools) == 2
        assert tools[0].name == "test_tool_1"
        assert tools[1].name == "test_tool_2"
        assert len(issues) == 0
