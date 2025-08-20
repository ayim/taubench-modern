from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(kw_only=True)
class ResponseReasoningContent(ResponseMessageContent):
    """Represents a reasoning segment in a model's response.

    Reasoning has enough provider-specific differences that we take a union
    of various fields (instead of trying to _force_ everything into a very
    consistent schema)."""

    reasoning: str | None = field(
        default=None,
        metadata={"description": "The reasoning text from the model"},
    )
    """The reasoning text from the model"""

    signature: str | None = field(
        default=None,
        metadata={"description": "The signature of the reasoning content"},
    )
    """The signature of the reasoning content"""

    redacted_content: str | None = field(
        default=None,
        metadata={"description": "The redacted content of the reasoning"},
    )
    """The redacted content of the reasoning"""

    encrypted_content: str | None = field(
        default=None,
        metadata={"description": "The encrypted content of the reasoning"},
    )
    """The encrypted content of the reasoning"""

    response_id: str | None = field(
        default=None,
        metadata={"description": "The response ID of the reasoning"},
    )
    """The response ID of the reasoning"""

    summary: list[str] | None = field(
        default=None,
        metadata={"description": "The summary of the reasoning"},
    )
    """The summary of the reasoning"""

    content: list[str] | None = field(
        default=None,
        metadata={"description": "The content of the reasoning"},
    )
    """The content of the reasoning"""

    kind: Literal["reasoning"] = field(
        default="reasoning",
        init=False,
        metadata={"description": "Content kind identifier, always 'reasoning'"},
    )
    """Content kind identifier, always 'reasoning'"""

    def __post_init__(self) -> None:
        """Validates the message kind after initialization.

        Raises:
            AssertionError: If the kind field doesn't match the literal "reasoning".
        """
        assert_literal_value_valid(self, "kind")

    def as_text_content(self) -> str:
        """Convert the response content to a text content."""
        return self.reasoning or "\n\n".join(self.summary or [])

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "reasoning": self.reasoning,
            "signature": self.signature,
            "redacted_content": self.redacted_content,
            "encrypted_content": self.encrypted_content,
            "response_id": self.response_id,
            "summary": self.summary,
            "content": self.content,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseReasoningContent":
        """Create a reasoning content from a dictionary."""
        data = data.copy()
        # Remove 'kind' if present since it's not an init parameter
        if "kind" in data:
            data.pop("kind")
        return cls(**data)


ResponseMessageContent.register_content_kind("reasoning", ResponseReasoningContent)
