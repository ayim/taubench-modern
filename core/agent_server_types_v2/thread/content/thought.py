from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.thread.content.base import ThreadMessageContent
from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass
class ThreadThoughtContent(ThreadMessageContent):
    """Represents a thought content item in a thread message.

    This class handles thought content, ensuring that the thought is non-empty
    and properly typed.
    """

    thought: str = field(metadata={"description": "The actual text content of the thought"})
    """The actual text content of the thought"""

    kind: Literal["thought"] = field(
        default="thought",
        metadata={"description": "Content kind: always 'thought'"},
        init=False,
    )
    """Content kind: always 'thought'"""

    def __post_init__(self) -> None:
        """Validates the content type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "thought".
            ValueError: If the text field is empty.
        """
        assert_literal_value_valid(self, "kind")

        if not self.thought:
            raise ValueError("Thought value cannot be empty")

    def as_text_content(self) -> str:
        """Converts the text content to a text content component."""
        return self.thought

    def to_json_dict(self) -> dict:
        """Serializes the text content to a dictionary. Useful for JSON serialization."""
        return {
            **super().to_json_dict(),
            "thought": self.thought,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThreadThoughtContent":
        """Create a thread thought content from a dictionary."""
        return cls(**data)


ThreadMessageContent.register_content_kind("thought", ThreadThoughtContent)