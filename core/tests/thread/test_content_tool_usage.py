import pytest

from agent_server_types_v2.thread.content.tool_usage import ThreadToolUsageContent


class TestThreadToolUsageContent:
    def test_create_valid_tool_usage_content(self):
        content = ThreadToolUsageContent(
            name="CalculatorTool",
            tool_call_id="call-123",
            arguments_raw='{"num1": 5, "num2": 7}',
            sub_type="action-external",
            status="running",
        )
        assert content.kind == "tool_call"
        assert content.status == "running"
        assert content.name == "CalculatorTool"
        assert content.tool_call_id == "call-123"

    def test_empty_tool_name_raises(self):
        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            ThreadToolUsageContent(
                name="",
                tool_call_id="call-999",
                arguments_raw='{}',
            )

    def test_as_text_content_for_finished_status_includes_result(self):
        content = ThreadToolUsageContent(
            name="TestTool",
            tool_call_id="call-xyz",
            arguments_raw='{"test": true}',
            status="finished",
            result="Some successful result",
        )
        text_obj = content.as_text_content()
        assert "TestTool" in text_obj
        assert "Some successful result" in text_obj

    def test_as_text_content_for_failed_status_includes_error(self):
        content = ThreadToolUsageContent(
            name="TestTool",
            tool_call_id="call-abc",
            arguments_raw='{"test": false}',
            status="failed",
            error="Something went wrong",
        )
        text_obj = content.as_text_content()
        assert "TestTool" in text_obj
        assert "Something went wrong" in text_obj
