from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from agent_platform_core.thread.base import ThreadMessage
from agent_platform_core.thread.content import ThreadThoughtContent
from agent_platform_core.utils import assert_literal_value_valid


@dataclass
class ThreadUserMessage(ThreadMessage):
    """Represents a user message in a thread."""

    role: Literal["user"] = field(
        default="user",
        metadata={"description": "The role of the message sender (always 'user')"},
    )
    """The role of the message sender (always 'user')"""

    def __post_init__(self) -> None:
        """Validates the message role after initialization.

        Raises:
            ValueError: If the role field doesn't match the literal "user".
        """
        assert_literal_value_valid(self, "role")

    def model_dump(self) -> dict:
        """Serializes the message to a dictionary. Useful for JSON serialization."""
        return {
            **super().model_dump(),
        }


@dataclass
class ThreadAgentMessage(ThreadMessage):
    """Represents an agent message in a thread."""

    role: Literal["agent"] = field(
        default="agent",
        metadata={"description": "The role of the message sender (always 'agent')"},
    )
    """The role of the message sender (always 'agent')"""

    def __post_init__(self) -> None:
        """Validates the message role after initialization.

        Raises:
            ValueError: If the role field doesn't match the literal "agent".
        """
        assert_literal_value_valid(self, "role")

    def append_thought(self, text_piece: str) -> None:
        """Adds a thought to the message. Appends to the last thought.

        Thought text shows up in a collapsible section in the UI
        near the beginning of the message. Similar to the o1 UX in
        ChatGPT.
        """
        # We cannot stream to a committed message!
        if self.commited:
            raise ValueError("Cannot add thought to a committed message")

        self.updated_at = datetime.now()

        for i, content in reversed(list(enumerate(self.content))):
            if isinstance(content, ThreadThoughtContent):
                self.content[i] = ThreadThoughtContent(
                    thought=content.thought + text_piece,
                )
                return

        self.content.append(ThreadThoughtContent(thought=text_piece))

    def new_thought(self, text_piece: str) -> None:
        """Adds a new thought to the message."""
        self.content.append(ThreadThoughtContent(thought=text_piece))

    def model_dump(self) -> dict:
        """Serializes the message to a dictionary. Useful for JSON serialization."""
        return {
            **super().model_dump(),
        }
