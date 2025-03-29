import json
from dataclasses import FrozenInstanceError

import pytest

from agent_platform.core.responses.content.text import ResponseTextContent


class TestResponseTextContent:
    """Tests for the ResponseTextContent class."""

    def test_init(self) -> None:
        """Test that ResponseTextContent initializes correctly."""
        content = ResponseTextContent(text="Hello, world!")
        assert content.text == "Hello, world!"
        assert content.kind == "text"

    def test_init_empty_text(self) -> None:
        """Test that ResponseTextContent raises an error for empty text."""
        with pytest.raises(ValueError, match="Text value cannot be empty"):
            ResponseTextContent(text="")

    def test_as_text_content(self) -> None:
        """Test that as_text_content returns the text."""
        content = ResponseTextContent(text="Hello, world!")
        assert content.as_text_content() == "Hello, world!"

    def test_model_dump(self) -> None:
        """Test that model_dump returns a dictionary with the text."""
        content = ResponseTextContent(text="Hello, world!")
        data = content.model_dump()
        assert data["kind"] == "text"
        assert data["text"] == "Hello, world!"

    def test_model_dump_json(self) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = ResponseTextContent(text="Hello, world!")
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "text"
        assert data["text"] == "Hello, world!"

    def test_model_validate(self) -> None:
        """Test that model_validate creates a ResponseTextContent from a dictionary."""
        data = {
            "kind": "text",
            "text": "Hello, world!",
        }  # 'kind' should be removed by model_validate
        content = ResponseTextContent.model_validate(data)
        assert isinstance(content, ResponseTextContent)
        assert content.kind == "text"
        assert content.text == "Hello, world!"

    def test_immutability(self) -> None:
        """Test that ResponseTextContent is immutable."""
        content = ResponseTextContent(text="Hello, world!")
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseTextContent is frozen
            content.text = "New text"  # type: ignore
