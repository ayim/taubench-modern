from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.utils import assert_literal_value_valid


@dataclass
class PromptReasoningContent(PromptMessageContent):
    """Represents a text message in the agent system.

    Reasoning has enough provider-specific differences that we take a union
    of various fields (instead of trying to _force_ everything into a very
    consistent schema).
    """

    reasoning: str | None = field(
        metadata={"description": "The actual reasoning content of the message"},
    )
    """The actual reasoning content of the message"""

    redacted_content: str | None = field(
        default=None,
        metadata={"description": "The redacted content of the message"},
    )
    """The redacted content of the message"""

    signature: str | None = field(
        default=None,
        metadata={"description": "The signature of the message"},
    )
    """The signature of the message"""

    encrypted_content: str | None = field(
        default=None,
        metadata={"description": "The encrypted content of the message"},
    )
    """The encrypted content of the message"""

    response_id: str | None = field(
        default=None,
        metadata={"description": "The response ID of the message"},
    )
    """The response ID of the message"""

    summary: list[str] | None = field(
        default=None,
        metadata={"description": "The summary of the message"},
    )
    """The summary of the message"""

    content: list[str] | None = field(
        default=None,
        metadata={"description": "The content of the message"},
    )
    """The content of the message"""

    kind: Literal["reasoning"] = field(
        default="reasoning",
        init=False,
        metadata={"description": "Message kind identifier, always 'reasoning'"},
    )
    """Message kind identifier, always 'reasoning'"""

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
            "reasoning": self.reasoning,
            "redacted_content": self.redacted_content,
            "signature": self.signature,
            "encrypted_content": self.encrypted_content,
            "response_id": self.response_id,
            "summary": self.summary,
            "content": self.content,
        }

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the text content.

        This method uses the shared token counting utility which attempts to use
        tiktoken (the OpenAI tokenizer) if available, otherwise falls back to a
        heuristic calculation.

        Returns:
            int: Estimated token count
        """
        # This probably looks a little funny... we can get reasoning in many
        # ways, and we're trying to account for them all. Some models give
        # us unredacted reasoning; othere's the content in chunks; other's
        # still a summary; and other's give the fully reasoning but only
        # in an encrypted form. Here's we mash everything we might get together
        # to try and have an (aggressive) over-estimate of what we might be sending.
        # (How models use reasoning in prompts is also tricky... depending on message
        # ordering reasoning tokens we send as input may be silently dropped.)
        raw_reasoning_text = self.reasoning or ""
        raw_reasoning_text += "\n\n" + "\n\n".join(self.summary or [])
        raw_reasoning_text += "\n\n" + "\n\n".join(self.content or [])
        raw_reasoning_text += "\n\n" + (self.redacted_content or "")
        raw_reasoning_text += "\n\n" + (self.encrypted_content or "")
        return PromptTextContent.count_tokens_in_text(raw_reasoning_text)

    @classmethod
    def model_validate(cls, data: dict) -> "PromptReasoningContent":
        """Create a reasoning content from a dictionary."""
        data = data.copy()
        return cls(**data)


# Register this content type with the base class
PromptMessageContent.register_content_kind("reasoning", PromptReasoningContent)
