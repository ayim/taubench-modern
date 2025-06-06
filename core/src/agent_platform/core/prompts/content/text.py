from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.prompts.utils import count_tokens_approx
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptTextContent(PromptMessageContent):
    """Represents a text message in the agent system.

    This class handles plain text content, ensuring that the text is non-empty
    and properly typed.
    """

    text: str = field(
        metadata={"description": "The actual text content of the message"},
    )
    """The actual text content of the message"""

    kind: Literal["text"] = field(
        default="text",
        init=False,
        metadata={"description": "Message kind identifier, always 'text'"},
    )
    """Message kind identifier, always 'text'"""

    def __post_init__(self) -> None:
        """Validates the message type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "text".
            ValueError: If the text field is empty.
        """
        assert_literal_value_valid(self, "kind")

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "text": self.text,
        }

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the text content.

        This method uses the shared token counting utility which attempts to use
        tiktoken (the OpenAI tokenizer) if available, otherwise falls back to a
        heuristic calculation.

        Returns:
            int: Estimated token count
        """
        return count_tokens_approx(self.text)

    @classmethod
    def model_validate(cls, data: dict) -> "PromptTextContent":
        """Create a text content from a dictionary."""
        data = data.copy()
        return cls(**data)


# Register this content type with the base class
PromptMessageContent.register_content_kind("text", PromptTextContent)
