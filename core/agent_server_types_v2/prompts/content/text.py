from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent
from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptTextContent(PromptMessageContent):
    """Represents a text message in the agent system.

    This class handles plain text content, ensuring that the text is non-empty
    and properly typed.
    """

    text: str = field(metadata={"description": "The actual text content of the message"})
    """The actual text content of the message"""

    type: Literal["text"] = field(default="text", metadata={"description": "Message type identifier, always 'text'"})
    """Message type identifier, always 'text'"""

    def __post_init__(self) -> None:
        """Validates the message type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "text".
            ValueError: If the text field is empty.
        """
        assert_literal_value_valid(self, "type")

        # Generally, we can't have an empty text value in our prompts
        # (Maybe there's a time to weaken this, but for now, let's keep it strict)
        if not self.text:
            raise ValueError("Text value cannot be empty")