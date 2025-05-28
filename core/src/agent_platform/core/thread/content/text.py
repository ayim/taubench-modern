import json
from dataclasses import dataclass, field

from agent_platform.core.thread.content.base import ContentDelta, ThreadMessageContent


@dataclass(frozen=True)
class Citation:
    """Represents a citation in the text content."""

    document_uri: str = field(
        metadata={"description": "The URI of the document that the citation is from"},
    )
    """The URI of the document that the citation is from"""

    start_char_index: int = field(
        metadata={
            "description": "The start character index of the citation in the document",
        },
    )
    """The start character index of the citation in the document"""

    end_char_index: int = field(
        metadata={
            "description": "The end character index of the citation in the document",
        },
    )
    """The end character index of the citation in the document"""

    cited_text: str | None = field(
        default=None,
        metadata={
            "description": "The text that is being cited (if provided, may be None)",
        },
    )
    """The text that is being cited (if provided, may be None)"""

    def model_dump(self) -> dict:
        """Serializes the citation to a dictionary. Useful for JSON serialization."""
        return {
            "document_uri": self.document_uri,
            "start_char_index": self.start_char_index,
            "end_char_index": self.end_char_index,
            "cited_text": self.cited_text,
        }

    def model_dump_json(self) -> str:
        """Serializes the citation to a JSON string."""
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict) -> "Citation":
        """Create a citation from a dictionary."""
        return cls(**data)


# TODO: Create a CitationDelta once needed (no current example of one from the models)


@dataclass
class ThreadTextContent(ThreadMessageContent):
    """Represents a text message in the thread.

    This class handles plain text content, ensuring that the text is non-empty
    and properly typed.
    """

    text: str = field(
        metadata={"description": "The actual text content of the message"},
    )
    """The actual text content of the message"""

    citations: list[Citation] = field(
        default_factory=list,
        metadata={"description": "The citations in the text content"},
    )
    """The citations in the text content"""

    kind: str = field(
        default="text",
        metadata={"description": "Content kind: always 'text'"},
        init=False,
    )
    """Content kind: always 'text'"""

    def __post_init__(self) -> None:
        """Validates the content type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "text".
            ValueError: If the text field is empty.
        """
        assert self.kind == "text"

        if not self.text:
            raise ValueError("Text value cannot be empty")

    def as_text_content(self) -> str:
        """Converts the text content to a text content component."""
        return self.text

    def model_dump(self) -> dict:
        """Serializes the text content to a dictionary.
        Useful for JSON serialization."""
        return {
            **super().model_dump(),
            "text": self.text,
            "citations": [citation.model_dump() for citation in self.citations],
        }

    def model_dump_json(self) -> str:
        """Serializes the text content to a JSON string."""
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadTextContent":
        """Create a thread text content from a dictionary."""
        data = data.copy()
        citations = [Citation.model_validate(citation) for citation in data.pop("citations", [])]
        return cls(**data, citations=citations)


@dataclass
class TextDelta(ContentDelta):
    """A delta for a thread text content."""

    kind: str = field(
        default="text",
        metadata={"description": "Content kind: always 'text'"},
        init=False,
    )
    """Content kind: always 'text'"""


ThreadMessageContent.register_content_kind("text", ThreadTextContent)
ContentDelta.register_content_kind("text", TextDelta)
