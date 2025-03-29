from dataclasses import dataclass, field
from json import dumps
from typing import ClassVar, Self

from agent_platform.core.delta import GenericDelta


@dataclass(frozen=True)
class ResponseMessageContent:
    """Base class for all model response content types.

    This class serves as the base for all content types that can be included
    in a model's response, such as text, images, audio, documents, and tool-related
    content. Each content type provides structured access to its specific data
    format and validation rules.
    """

    _content_kinds: ClassVar[dict[str, type["ResponseMessageContent"]]] = {}

    kind: str = field(
        default="",
        metadata={"description": "The kind of the response content"},
        init=False,
    )
    """The kind of the response content"""

    # TODO: Consider if this is useful, I did not use this in the examples
    uncommitted_deltas: list[GenericDelta] = field(
        default_factory=list,
        metadata={"description": "The uncommitted deltas for the content"},
        init=False,
    )
    """The uncommitted deltas for the content"""

    def append(self, delta: GenericDelta) -> None:
        """Append a delta to the response content."""
        self.uncommitted_deltas.append(delta)

    def extend(self, deltas: list[GenericDelta]) -> None:
        """Extend the response content with a list of deltas."""
        self.uncommitted_deltas.extend(deltas)

    def commit_deltas(self) -> None:
        """Commit the uncommitted deltas to the response content."""
        if not self.is_dirty:
            return

    @property
    def is_dirty(self) -> bool:
        """Whether the content has uncommitted deltas."""
        return bool(self.uncommitted_deltas)

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        # TODO: Should we commit them, dump them, or raise an error?
        if self.is_dirty:
            raise ValueError("Cannot serialize dirty content")
        return {
            "kind": self.kind,
        }

    def model_dump_json(self) -> str:
        """Returns a JSON string representation of the content."""
        return dumps(self.model_dump())

    def model_copy(self) -> Self:
        """Returns a deep copy of the response content."""
        cls = type(self)
        dict_no_kind = self.model_dump()
        dict_no_kind.pop("kind")
        return cls.model_validate(dict_no_kind)

    @classmethod
    def register_content_kind(
        cls,
        kind_name: str,
        content_class: type["ResponseMessageContent"],
    ) -> None:
        """Register a content kind with its corresponding class.

        Args:
            kind_name: The string identifier for the content kind
            content_class: The class that handles this content kind
        """
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseMessageContent":
        """Create a response message content from a dictionary.

        Args:
            data: Dictionary containing the content data, must include a 'kind' field

        Returns:
            An instance of the appropriate ResponseMessageContent subclass

        Raises:
            ValueError: If the content type is not recognized
        """
        data = data.copy()
        kind = data.pop("kind")
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        content_class = cls._content_kinds[kind]
        return content_class.model_validate(data)
