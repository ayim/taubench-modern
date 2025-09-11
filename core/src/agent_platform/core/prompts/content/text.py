import math
from dataclasses import dataclass, field
from typing import Literal

from structlog import get_logger

from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.utils import assert_literal_value_valid

logger = get_logger(__name__)


@dataclass
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
        """Counts the approximate number of tokens in the text content."""
        return PromptTextContent.count_tokens_in_text(self.text)

    @classmethod
    def model_validate(cls, data: dict) -> "PromptTextContent":
        """Create a text content from a dictionary."""
        data = data.copy()
        return cls(**data)

    @staticmethod
    def count_tokens_in_text(text: str, safety_factor: float = 1.3) -> int:
        """Counts the approximate number of tokens in the text content."""
        from tiktoken import get_encoding

        try:
            encoding = get_encoding("o200k_base")
            return math.ceil(len(encoding.encode(text)) * safety_factor)
        except Exception as e:
            logger.error(f"Error counting tokens in text: {e!r}")
            # Fallback to conservative heuristic:
            # Estimate based on characters and words, pick the bigger of the two
            # and then inflate it by a safety factor so we don't undershoot. This
            # hueristics is the one recommended by OpenAI for their API.
            char_count = len(text)
            word_count = len(text.split())
            return math.ceil(max(char_count / 4, word_count / 0.75) * safety_factor)


# Register this content type with the base class
PromptMessageContent.register_content_kind("text", PromptTextContent)
