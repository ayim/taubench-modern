from dataclasses import dataclass, field
from typing import Literal

from agent_platform_core.responses.content.base import ResponseMessageContent
from agent_platform_core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class ResponseTextContent(ResponseMessageContent):
    """Represents a text segment in a model's response.

    This class handles plain text content from the model's response, ensuring that
    the text is non-empty and properly typed.
    """

    text: str = field(
        metadata={"description": "The actual text content from the model"},
    )
    """The actual text content from the model"""

    kind: Literal["text"] = field(
        default="text",
        init=False,
        metadata={"description": "Content kind identifier, always 'text'"},
    )
    """Content kind identifier, always 'text'"""

    def __post_init__(self) -> None:
        """Validates the message kind and text content after initialization.

        Raises:
            AssertionError: If the kind field doesn't match the literal "text".
            ValueError: If the text field is empty.
        """
        assert_literal_value_valid(self, "kind")

        # Generally, we can't have an empty text value in model responses
        if not self.text:
            raise ValueError("Text value cannot be empty")

    def as_text_content(self) -> str:
        """Convert the response content to a text content."""
        return self.text

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "text": self.text,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseTextContent":
        """Create a text content from a dictionary."""
        data = data.copy()
        # Remove 'kind' if present since it's not an init parameter
        if "kind" in data:
            data.pop("kind")
        return cls(**data)


ResponseMessageContent.register_content_kind("text", ResponseTextContent)
