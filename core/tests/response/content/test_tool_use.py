import json

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent


class TestResponseToolUseContent:
    """Tests for the ResponseToolUseContent class."""

    def test_init(self) -> None:
        """Test that ResponseToolUseContent initializes correctly."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "param2": 42}',
        )
        assert content.tool_call_id == "123"
        assert content.tool_name == "test_tool"
        assert content.tool_input_raw == '{"param1": "value1", "param2": 42}'
        assert content.kind == "tool_use"
        assert content.tool_input == {"param1": "value1", "param2": 42}

    def test_init_empty_args(self) -> None:
        """Test that ResponseToolUseContent initializes correctly with empty args."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw="",
        )
        assert content.tool_input_raw == "{}"
        assert content.tool_input == {}

    def test_init_normalize_empty_keys(self) -> None:
        """Test that ResponseToolUseContent normalizes empty keys."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "": "blah"}',
        )
        assert content.tool_input_raw == '{"param1": "value1"}'
        assert content.tool_input == {"param1": "value1"}

    def test_init_invalid_json_tolerated(self) -> None:
        """Invalid JSON is tolerated; tool_input remains empty and raw preserved."""
        partial = '{"param1": "value1", "param2": 42'
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw=partial,
        )
        assert content.tool_input == {}
        assert content.tool_input_raw == partial

    def test_tool_input_property(self) -> None:
        """Test that tool_input property returns the parsed tool input."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "param2": 42}',
        )
        assert content.tool_input == {"param1": "value1", "param2": 42}

    def test_model_dump(self) -> None:
        """Test that model_dump returns a dictionary with the tool use data."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "param2": 42}',
        )
        data = content.model_dump()
        assert data["kind"] == "tool_use"
        assert data["tool_call_id"] == "123"
        assert data["tool_name"] == "test_tool"
        assert data["tool_input_raw"] == '{"param1": "value1", "param2": 42}'

    def test_model_dump_json(self) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "param2": 42}',
        )
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "tool_use"
        assert data["tool_call_id"] == "123"
        assert data["tool_name"] == "test_tool"
        assert data["tool_input_raw"] == '{"param1": "value1", "param2": 42}'

    def test_model_validate(self) -> None:
        """Test that model_validate creates a ResponseToolUseContent
        from a dictionary."""
        data = {
            "kind": "tool_use",  # This should be removed by model_validate
            "tool_call_id": "123",
            "tool_name": "test_tool",
            "tool_input_raw": '{"param1": "value1", "param2": 42}',
        }
        content = ResponseToolUseContent.model_validate(data)
        assert isinstance(content, ResponseToolUseContent)
        assert content.kind == "tool_use"
        assert content.tool_call_id == "123"
        assert content.tool_name == "test_tool"
        assert content.tool_input_raw == '{"param1": "value1", "param2": 42}'
        assert content.tool_input == {"param1": "value1", "param2": 42}

    def test_init_allows_partial_json(self) -> None:
        """Partial JSON should not raise; tool_input empty and raw preserved."""
        partial = '{"markdown":  "This is an encoded string possibly... and I want to get text'
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="writer",
            tool_input_raw=partial,
        )
        assert content.tool_input == {}
        assert content.tool_input_raw == partial
