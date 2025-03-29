import json
from dataclasses import FrozenInstanceError

import pytest

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

    def test_init_invalid_json(self) -> None:
        """Test that ResponseToolUseContent raises an error for invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            ResponseToolUseContent(
                tool_call_id="123",
                tool_name="test_tool",
                tool_input_raw='{"param1": "value1", "param2": 42',
                # ^ Missing closing brace
            )

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

    def test_immutability(self) -> None:
        """Test that ResponseToolUseContent is immutable."""
        content = ResponseToolUseContent(
            tool_call_id="123",
            tool_name="test_tool",
            tool_input_raw='{"param1": "value1", "param2": 42}',
        )
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseToolUseContent is frozen
            content.tool_name = "new_tool"  # type: ignore
