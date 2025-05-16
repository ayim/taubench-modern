from dataclasses import dataclass, field
from json import dumps
from typing import ClassVar


@dataclass(frozen=True)
class PromptMessageContent:
    """Base class for all prompt message content types."""

    _content_kinds: ClassVar[dict[str, type["PromptMessageContent"]]] = {}

    kind: str = field(
        default="",
        metadata={"description": "The kind of the prompt message content"},
        init=False,
    )
    """The kind of the prompt message content"""

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            "kind": self.kind,
        }

    def model_dump_json(self) -> str:
        """Returns a JSON string representation of the content."""
        return dumps(self.model_dump())

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the content."""
        # This is a placeholder for subclasses to implement
        return 0

    @classmethod
    def register_content_kind(
        cls,
        kind_name: str,
        content_class: type["PromptMessageContent"],
    ) -> None:
        """Register a content kind with its corresponding class.

        Args:
            kind_name: The string identifier for the content kind
            content_class: The class that handles this content kind
        """
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def model_validate(cls, data: dict) -> "PromptMessageContent":
        """Create a prompt message content from a dictionary.

        Args:
            data: Dictionary containing the content data, must include a 'kind' field

        Returns:
            An instance of the appropriate PromptMessageContent subclass

        Raises:
            ValueError: If the content type is not recognized
        """
        data = data.copy()
        kind = data.pop("kind")
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        content_class = cls._content_kinds[kind]
        return content_class.model_validate(data)
