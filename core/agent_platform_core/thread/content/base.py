import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Self
from uuid import uuid4

from agent_platform_core.delta import GenericDelta


@dataclass
class ThreadMessageContent(ABC):
    """Base class for all thread message content types."""

    _content_kinds: ClassVar[dict[str, type["ThreadMessageContent"]]] = {}

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

    uncommitted_deltas: list[GenericDelta] = field(
        default_factory=list,
        metadata={"description": "The uncommitted deltas for the content"},
        init=False,
    )
    """The uncommitted deltas for the content"""

    @abstractmethod
    def as_text_content(self) -> str:
        """Converts the thread message content to a string."""
        pass

    def append(self, delta: GenericDelta) -> None:
        """Appends a delta to the content, does not commit it."""
        self.uncommitted_deltas.append(delta)

    def extend(self, deltas: list[GenericDelta]) -> None:
        """Appends a list of deltas to the content, does not commit them."""
        self.uncommitted_deltas.extend(deltas)

    def commit_deltas(self) -> None:
        """Commits the uncommitted deltas to the content.

        This is a generic implementation that can be overriden by
        concrete content types.
        """
        if not self.is_dirty:
            return

    @property
    def is_dirty(self) -> bool:
        """Whether the content has uncommitted deltas."""
        return bool(self.uncommitted_deltas)

    def model_dump(self) -> dict:
        """Serializes the content to a dictionary. Useful for JSON serialization."""
        # TODO: Should we commit them, dump them, or raise an error?
        if self.is_dirty:
            raise ValueError("Cannot serialize dirty content")
        return {
            "content_id": self.content_id,
            "kind": self.kind,
        }

    def model_dump_json(self) -> str:
        """Serializes the content to a JSON string."""
        return json.dumps(self.model_dump())

    def model_copy(self) -> Self:
        """Returns a deep copy of the message content."""
        cls = type(self)
        dict_no_content_id_kind = self.model_dump()
        dict_no_content_id_kind.pop("content_id")
        dict_no_content_id_kind.pop("kind")
        new_content = cls(**dict_no_content_id_kind)
        new_content.content_id = self.content_id
        return new_content

    @classmethod
    def register_content_kind(
        cls,
        kind_name: str,
        content_class: type["ThreadMessageContent"],
    ) -> None:
        """Register a content kind with its corresponding class.

        Args:
            kind_name: The string identifier for the content kind
            content_class: The class that handles this content kind
        """
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadMessageContent":
        """Create a thread message content from a dictionary.

        Args:
            data: Dictionary containing the content data, must include a 'kind' field

        Returns:
            An instance of the appropriate ThreadMessageContent subclass

        Raises:
            ValueError: If the content type is not recognized
        """
        kind = data.pop("kind")
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        content_id = data.pop("content_id", str(uuid4()))

        content_class = cls._content_kinds[kind]
        result = content_class.model_validate(data)
        result.content_id = content_id
        return result


@dataclass
class ContentDelta(ABC):
    """A delta for a thread message content.

    This type is used to represent incoming message parts to be applied
    to the current thread. The most common use case is for streaming
    tokens from a model into the thread.
    """

    _content_kinds: ClassVar[dict[str, type["ContentDelta"]]] = {}

    delta: GenericDelta = field(
        metadata={"description": "The delta to apply to the content."},
    )
    """The delta to apply to the content."""

    sequence_number: int = field(
        metadata={"description": "The sequence number of the delta."},
    )
    """The sequence number of the delta."""

    parent_id: str | None = field(
        default=None,
        metadata={"description": "The unique identifier of the parent content."},
    )
    """The unique identifier of the parent content."""

    delta_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={
            "description": "The unique identifier of the delta. If not provided "
            "(e.g., from the model), one will be generated.",
        },
    )
    """The unique identifier of the delta. If not provided
    (e.g., from the model), one will be generated."""

    kind: str = field(
        default="",
        metadata={"description": "The kind of the content delta."},
        init=False,
    )
    """The kind of the content delta."""

    timestamp: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "The timestamp of the delta."},
        init=False,
    )
    """The timestamp of the delta."""

    def model_dump(self) -> dict:
        return {
            "content_id": self.content_id,
            "delta_id": self.delta_id,
            "kind": self.kind,
            "delta": self.delta.model_dump(),
            "timestamp": self.timestamp,
        }

    def model_copy(self) -> Self:
        """Returns a deep copy of the content delta."""
        cls = type(self)
        dict_no_content_id_delta_id = self.model_dump()
        dict_no_content_id_delta_id.pop("content_id")
        dict_no_content_id_delta_id.pop("delta_id")
        return cls.model_validate(dict_no_content_id_delta_id)

    @classmethod
    def register_content_kind(
        cls,
        kind_name: str,
        content_class: type["ContentDelta"],
    ) -> None:
        """Register a content kind with its corresponding class."""
        cls._content_kinds[kind_name] = content_class

    @classmethod
    def model_validate(cls, data: dict) -> "ContentDelta":
        """Create a content delta from a dictionary.

        Args:
            data: Dictionary containing the content delta data

        Returns:
            An instance of the appropriate ContentDelta subclass

        Raises:
            ValueError: If the content type is not recognized
        """
        kind = data.pop("kind")
        if kind not in cls._content_kinds:
            raise ValueError(f"Unknown content kind: {kind}")

        parent_id = data.pop("parent_id", None)
        delta_id = data.pop("delta_id", str(uuid4()))
        timestamp = data.pop("timestamp", datetime.now())

        delta_class = cls._content_kinds[kind]
        result = delta_class.model_validate(data)
        result.parent_id = parent_id
        result.delta_id = delta_id
        result.timestamp = timestamp
        return result

    @abstractmethod
    def as_thread_message_content(self) -> "ThreadMessageContent":
        """Convert the content delta to a thread message content."""
        pass
