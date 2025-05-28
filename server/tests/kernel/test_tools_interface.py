"""Tests for the AgentServerToolsInterface class."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition
from agent_platform.server.kernel.tools import AgentServerToolsInterface


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


@pytest.fixture
def tools_interface(mock_kernel):
    """Create a tools interface for testing."""
    interface = AgentServerToolsInterface()
    interface.attach_kernel(mock_kernel)
    return interface


@pytest.mark.asyncio
async def test_internal_error_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="error_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error == "internal-error: test exception!"
    assert result.output_raw == {
        "error_code": "internal-error",
        "message": "test exception!",
    }
    assert result.definition == tool_def
    assert result.tool_call_id == "call_123"


@pytest.mark.asyncio
async def test_validation_error_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_456",
        tool_name="validation_error_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify the error is properly handled
    assert result.error is not None
    assert result.error.startswith("validation-error: The received input arguments")
    assert result.output_raw is not None
    assert result.output_raw["error_code"] == "validation-error"
    assert result.definition == tool_def
    assert result.tool_call_id == "call_456"


@pytest.mark.asyncio
async def test_error_in_execute_pending_tool_calls():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_789",
        tool_name="error_tool",
        tool_input_raw="{}",
    )

    # Execute pending tool calls
    pending_calls = [(tool_def, tool_use)]
    results = []

    async for result in interface.execute_pending_tool_calls(pending_calls):
        results.append(result)

    # Verify the error is properly handled
    assert len(results) == 1
    assert results[0].error == "test-error: Test error message"
    assert results[0].output_raw == {
        "error_code": "test-error",
        "message": "Test error message",
    }


@pytest.mark.asyncio
async def test_malformed_json_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Patch the ToolExecutionResult.__post_init__ method to handle invalid JSON
    with patch(
        "agent_platform.core.tools.tool_execution_result.ToolExecutionResult.__post_init__"
    ) as mock_post_init:
        # Make post_init do nothing (skip JSON parsing)
        mock_post_init.return_value = None

        # Create a tool use request with malformed JSON
        tool_use = MagicMock(spec=ResponseToolUseContent)
        tool_use.tool_call_id = "call_invalid"
        tool_use.tool_name = "sample_tool"
        tool_use.tool_input_raw = "{invalid json"

        # Execute the tool with our mocked request
        result = await interface._safe_execute_tool(tool_def, tool_use)

        # Verify the error is properly handled
        assert result.error is not None
        assert "Expecting property name" in result.error or "Unterminated string" in result.error
        assert result.output_raw is None

        # Verify our mock was called
        mock_post_init.assert_called()


@pytest.mark.asyncio
async def test_tool_exception_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_exception",
        tool_name="exception_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify the exception is properly handled
    assert result.error == "Unexpected error during execution"
    assert result.output_raw is None


@pytest.mark.asyncio
async def test_none_result_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_none",
        tool_name="none_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify None is properly handled
    assert result.error is None
    assert result.output_raw is None
    assert result.definition == tool_def
    assert result.tool_call_id == "call_none"


@pytest.mark.asyncio
async def test_string_result_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_string",
        tool_name="string_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify string is properly handled
    assert result.error is None
    assert result.output_raw == "Hello, world!"
    assert result.definition == tool_def
    assert result.tool_call_id == "call_string"


@pytest.mark.asyncio
async def test_integer_result_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_integer",
        tool_name="integer_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify integer is properly handled
    assert result.error is None
    assert result.output_raw == 42
    assert result.definition == tool_def
    assert result.tool_call_id == "call_integer"


@pytest.mark.asyncio
async def test_float_result_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_float",
        tool_name="float_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify float is properly handled
    assert result.error is None
    assert result.output_raw == 3.14159
    assert result.definition == tool_def
    assert result.tool_call_id == "call_float"


@pytest.mark.asyncio
async def test_boolean_result_handling():
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

        # Create the tools interface
        interface = AgentServerToolsInterface()
        mock_kernel = MagicMock()
        mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
        mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
        interface.attach_kernel(mock_kernel)

        # Create a tool use request
        tool_use = ResponseToolUseContent(
            tool_call_id=f"call_{tool_name}",
            tool_name=tool_name,
            tool_input_raw="{}",
        )

        # Execute the tool
        result = await interface._safe_execute_tool(tool_def, tool_use)

        # Verify boolean is properly handled
        assert result.error is None
        assert result.output_raw == bool_value
        assert result.definition == tool_def
        assert result.tool_call_id == f"call_{tool_name}"


@pytest.mark.asyncio
async def test_malformed_result_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_malformed",
        tool_name="malformed_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify malformed result is properly handled
    assert result.error == "Received a malformed result from the tool"
    assert result.output_raw == ["this", "is", "a", "list"]
    assert result.definition == tool_def
    assert result.tool_call_id == "call_malformed"


@pytest.mark.asyncio
async def test_dict_with_empty_error_code_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_success_dict",
        tool_name="success_dict_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify dict with empty error_code is treated as successful
    assert result.error is None
    assert result.output_raw == {"error_code": "", "data": "success", "count": 5}
    assert result.definition == tool_def
    assert result.tool_call_id == "call_success_dict"


@pytest.mark.asyncio
async def test_dict_without_error_code_handling():
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

    # Create the tools interface
    interface = AgentServerToolsInterface()
    mock_kernel = MagicMock()
    mock_kernel.ctx.start_span.return_value.__enter__ = MagicMock()
    mock_kernel.ctx.start_span.return_value.__exit__ = MagicMock()
    interface.attach_kernel(mock_kernel)

    # Create a tool use request
    tool_use = ResponseToolUseContent(
        tool_call_id="call_normal_dict",
        tool_name="normal_dict_tool",
        tool_input_raw="{}",
    )

    # Execute the tool
    result = await interface._safe_execute_tool(tool_def, tool_use)

    # Verify dict without error_code is treated as successful
    assert result.error is None
    assert result.output_raw == {
        "result": "success",
        "data": {"key": "value"},
        "status": "ok",
    }
    assert result.definition == tool_def
    assert result.tool_call_id == "call_normal_dict"
