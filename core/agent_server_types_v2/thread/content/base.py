from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Self
from uuid import uuid4


@dataclass
class ThreadMessageContent(ABC):
    """Base class for all thread message content types."""

    _content_kinds: ClassVar[dict] = {}

    content_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={"description": "The unique identifier of the content"},
        init=False,
    )
    """The unique identifier of the content"""

    kind: str = field(
        default="",
        metadata={"description": "The kind of the thread message content"},
        init=False,
    )
    """The kind of the thread message content"""

    @abstractmethod
    def as_text_content(self) -> str:
        """Converts the thread message content to a string."""
        pass

    def to_json_dict(self) -> dict:
        """Serializes the content to a dictionary. Useful for JSON serialization."""
        return {
            "content_id": self.content_id,
            "kind": self.kind,
        }

    def copy(self) -> Self:
        """Returns a deep copy of the message content."""
        cls = type(self)
        dict_no_content_id_kind = self.to_json_dict()
        dict_no_content_id_kind.pop("content_id")
        dict_no_content_id_kind.pop("kind")
        new_content = cls(**dict_no_content_id_kind)
        new_content.content_id = self.content_id
        return new_content
    
    @classmethod
    def register_content_kind(cls, kind_name: str, content_class: type["ThreadMessageContent"]) -> None:
        """Register a content kind with its corresponding class.
        
        Args:
            kind_name: The string identifier for the content kind
            content_class: The class that handles this content kind
        """
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def from_dict(cls, data: dict) -> "ThreadMessageContent":
        """Create a thread message content from a dictionary.
        
        Args:
            data: Dictionary containing the content data, must include a 'kind' field
            
        Returns:
            An instance of the appropriate ThreadMessageContent subclass
            
        Raises:
            ValueError: If the content type is not recognized
        """
        kind = data.pop('kind')
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        content_id = data.pop("content_id", str(uuid4()))

        content_class = cls._content_kinds[kind]
        result = content_class.from_dict(data)
        result.content_id = content_id
        return result
