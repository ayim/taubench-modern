from base64 import b64decode
from dataclasses import dataclass, field
from typing import Literal

# from agent_server_types_v2.files import UploadedFile
from agent_server_types_v2.prompts.content.base import PromptMessageContent
from agent_server_types_v2.utils.asserts import assert_literal_value_valid

# TODO: Remove this once the files module is implemented
UploadedFile = type[None]


@dataclass(frozen=True)
class PromptDocumentContent(PromptMessageContent):
    """Represents a document message in the agent system.

    This class handles document content in either URL or base64 format, with support
    for different resolutions and image formats.
    """

    mime_type: Literal[
        "application/pdf",
        "text/plain",
        "text/csv",
        "text/tab-separated-values",
        "text/markdown",
        "text/html",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ] = field(
        metadata={"description": "MIME type of the document"},
    )
    """MIME type of the document"""

    value: str | bytes | UploadedFile = field(
        metadata={
            "description": "The document data - either an agent-server UploadedFile, "
            "base64 encoded string, or raw bytes",
        },
    )
    """The document data - either an agent-server UploadedFile, base64 encoded string,
    or raw bytes"""

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

    sub_type: Literal["UploadedFile", "base64", "raw_bytes", "url"] = field(
        default="UploadedFile",
        metadata={
            "description": "Format of the document data - either an agent-server "
            "UploadedFile, base64 encoded string, raw bytes, or URL",
        },
    )
    """Format of the document data - either an agent-server UploadedFile, base64
    encoded string, raw bytes, or URL"""

    def __post_init__(self) -> None:  # noqa: C901
        """Validates the document content after initialization.

        Performs validation of literal values and ensures the document value is valid.
        """
        assert_literal_value_valid(self, "kind")
        assert_literal_value_valid(self, "sub_type")
        assert_literal_value_valid(self, "mime_type")

        # Check for empty value
        if not self.value:
            raise ValueError("Document value cannot be empty")

        # Validate UploadedFile if applicable
        if self.sub_type == "UploadedFile":
            if not isinstance(self.value, UploadedFile):
                raise ValueError("Document value must be an agent-server UploadedFile")

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

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "mime_type": self.mime_type,
            "value": self.value,
            "name": self.name,
            "sub_type": self.sub_type,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "PromptDocumentContent":
        """Create a document content from a dictionary."""
        data = data.copy()
        return cls(**data)


# Register this content type with the base class
PromptMessageContent.register_content_kind("document", PromptDocumentContent)
