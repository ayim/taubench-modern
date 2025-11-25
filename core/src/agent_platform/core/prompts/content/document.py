from base64 import b64decode
from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.files.mime_types import PromptDocumentMimeTypeLiteral
from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.utils.asserts import assert_literal_value_valid


@dataclass
class PromptDocumentContent(PromptMessageContent):
    """Represents a document message in the agent system.

    This class handles document content in either URL or base64 format, with support
    for different resolutions and image formats.
    """

    mime_type: PromptDocumentMimeTypeLiteral = field(
        metadata={"description": "MIME type of the document"},
    )
    """MIME type of the document"""

    # TODO Reintroduce UploadedFile when we have a way to leverage FileService properly
    value: str | bytes = field(
        metadata={
            "description": "The document data - either a base64 encoded string, or raw bytes",
        },
    )
    """The document data - either a base64 encoded string or raw bytes"""

    name: str = field(
        metadata={
            "description": "The name of the document",
        },
    )
    """The name of the document"""

    kind: Literal["document"] = field(
        default="document",
        init=False,
        metadata={"description": "Message kind identifier, always 'document'"},
    )
    """Message kind identifier, always 'document'"""

    sub_type: Literal["base64", "raw_bytes", "url"] = field(
        default="base64",
        metadata={
            "description": "Format of the document data - either an agent-server "
            "base64 encoded string, raw bytes, or URL",
        },
    )
    """Format of the document data - either an agent-server UploadedFile, base64
    encoded string, raw bytes, or URL"""

    def __post_init__(self) -> None:
        """Validates the document content after initialization.

        Performs validation of literal values and ensures the document value is valid.
        """
        assert_literal_value_valid(self, "kind")
        assert_literal_value_valid(self, "sub_type")
        assert_literal_value_valid(self, "mime_type")

        # Check for empty value
        if not self.value:
            raise ValueError("Document value cannot be empty")

        # Validate base64 data if applicable
        if self.sub_type == "base64":
            try:
                b64decode(self.value, validate=True)
            except Exception as e:
                raise ValueError("Document value is not a valid base64 string") from e

        # Validate raw bytes if applicable
        if self.sub_type == "raw_bytes":
            if not isinstance(self.value, bytes):
                raise ValueError("Document value must be bytes")

        # Validate URL if applicable
        if self.sub_type == "url":
            if not isinstance(self.value, str):
                raise ValueError("Document value must be a string")
            if not self.value.startswith("http"):
                raise ValueError("Document value must be a valid URL")

            from urllib.parse import urlparse

            try:
                urlparse(self.value)
            except Exception as e:
                raise ValueError("Document value must be a valid URL") from e

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "mime_type": self.mime_type,
            "value": self.value,
            "name": self.name,
            "sub_type": self.sub_type,
        }

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the document content."""
        # TODO: Implement this, we do not currently count document content
        return 0

    @classmethod
    def model_validate(cls, data: dict) -> "PromptDocumentContent":
        """Create a document content from a dictionary."""
        data = data.copy()
        return cls(**data)


# Register this content type with the base class
PromptMessageContent.register_content_kind("document", PromptDocumentContent)
