from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Self


@dataclass
class RunbookContent(ABC):
    """Base class for all runbook content types."""

    _content_kinds: ClassVar[dict[str, type["RunbookContent"]]] = {}

    kind: str = field(
        default="",
        metadata={"description": "The kind of the runbook content"},
        init=False,
    )
    """The kind of the runbook content"""

    @abstractmethod
    def model_dump(self) -> dict:
        """Serializes the runbook content to a dictionary.
        Useful for JSON serialization."""

    @abstractmethod
    def copy(self) -> Self:
        """Returns a deep copy of the runbook content."""

    @classmethod
    def register_content_kind(
        cls,
        kind_name: str,
        content_class: type["RunbookContent"],
    ) -> None:
        """Register a content kind with its corresponding class.

        Args:
            kind_name: The string identifier for the content kind
            content_class: The class that handles this content kind
        """
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookContent":
        """Create a runbook text content from a dictionary.

        Args:
            data: Dictionary containing the content data, must include a 'kind' field

        Returns:
            An instance of the appropriate RunbookContent subclass

        Raises:
            ValueError: If the content type is not recognized
        """
        data = data.copy()
        kind = data.pop("kind")
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        content_class = cls._content_kinds[kind]
        return content_class.model_validate(data)
