from base64 import b64decode
from dataclasses import dataclass, field
from typing import Literal

# from agent_platform.core.files import UploadedFile
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.utils.asserts import assert_literal_value_valid

ResponseDocumentMimeTypes = Literal[
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
]

RESPONSE_DOCUMENT_MIME_TYPES: set[ResponseDocumentMimeTypes] = {
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
}


@dataclass(kw_only=True)
class ResponseDocumentContent(ResponseMessageContent):
    """Represents a document generated or referenced in a model's response.

    This class handles document content in various formats (URL, base64, raw bytes),
    supporting a wide range of document types including PDFs, text files, spreadsheets,
    and word processing documents. It provides validation and format handling for
    document data.
    """

    mime_type: ResponseDocumentMimeTypes = field(
        metadata={"description": "MIME type of the document"},
    )
    """MIME type of the document"""

    value: str | bytes = field(
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
        metadata={"description": "Content kind identifier, always 'document'"},
    )
    """Content kind identifier, always 'document'"""

    sub_type: Literal["UploadedFile", "base64", "raw_bytes", "url"] = field(
        default="UploadedFile",
        metadata={
            "description": "Format of the document data - either an agent-server "
            "UploadedFile, base64 encoded string, raw bytes, or URL",
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

        # Validate UploadedFile if applicable
        if self.sub_type == "UploadedFile":
            raise NotImplementedError("UploadedFile is not implemented")

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
            if not (isinstance(self.value, str) and self.value.startswith("http")):
                raise ValueError("Document value must be a string and start with http")

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
    def model_validate(cls, data: dict) -> "ResponseDocumentContent":
        """Create a document content from a dictionary."""
        data = data.copy()
        # Remove 'kind' if present since it's not an init parameter
        if "kind" in data:
            data.pop("kind")
        return cls(**data)


ResponseMessageContent.register_content_kind("document", ResponseDocumentContent)
