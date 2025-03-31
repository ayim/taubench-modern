import json
from dataclasses import dataclass, field
from typing import Literal

import pytest

from agent_platform.core.responses.content.base import ResponseMessageContent


# Create a simple concrete implementation for testing
@dataclass(frozen=True)
class MockContent(ResponseMessageContent):
    """A simple content implementation for testing."""

    value: str = field(metadata={"description": "Test value"})
    kind: Literal["test"] = field(
        default="test",
        init=False,
        metadata={"description": "Content kind identifier, always 'test'"},
    )

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "value": self.value,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "MockContent":
        """Create a test content from a dictionary."""
        data = data.copy()
        return cls(**data)


# Register the test content kind
ResponseMessageContent.register_content_kind("test", MockContent)


class TestResponseMessageContent:
    """Tests for the ResponseMessageContent base class."""

    def test_register_content_kind(self) -> None:
        """Test that content kinds can be registered."""
        assert "test" in ResponseMessageContent._content_kinds
        assert ResponseMessageContent._content_kinds["test"] == MockContent

    def test_model_validate(self) -> None:
        """Test that model_validate creates the correct content type."""
        data = {"kind": "test", "value": "test value"}
        content = ResponseMessageContent.model_validate(data)
        assert isinstance(content, MockContent)
        assert content.kind == "test"
        assert content.value == "test value"

    def test_model_validate_unknown_kind(self) -> None:
        """Test that model_validate raises an error for unknown kinds."""
        data = {"kind": "unknown", "value": "test value"}
        with pytest.raises(ValueError, match="Unknown content kind: unknown"):
            ResponseMessageContent.model_validate(data)

    def test_model_validate_missing_kind(self) -> None:
        """Test that model_validate raises an error when kind is missing."""
        data = {"value": "test value"}
        with pytest.raises(KeyError):
            ResponseMessageContent.model_validate(data)

    def test_model_dump(self) -> None:
        """Test that model_dump returns a dictionary with the kind."""
        content = MockContent(value="test value")
        data = content.model_dump()
        assert data["kind"] == "test"
        assert data["value"] == "test value"

    def test_model_dump_json(self) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = MockContent(value="test value")
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "test"
        assert data["value"] == "test value"

    def test_model_copy(self) -> None:
        """Test that model_copy returns a copy of the content."""
        content = MockContent(value="test value")
        copy = content.model_copy()
        assert copy is not content
        assert copy.model_dump() == content.model_dump()
