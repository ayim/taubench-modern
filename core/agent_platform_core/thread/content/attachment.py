from dataclasses import dataclass, field
from typing import Literal

from agent_platform_core.thread.content.base import ThreadMessageContent
from agent_platform_core.utils import assert_literal_value_valid


@dataclass
class ThreadAttachmentContent(ThreadMessageContent):
    """Represents an attachment (file/image/etc) in the thread.

    This class handles attachements, allowing threads to include files/images/etc.
    at any point in the thread.
    """

    name: str = field(metadata={"description": "The name of the attachment"})
    """The name of the attachment"""

    mime_type: str = field(metadata={"description": "The MIME type of the attachment"})
    """The MIME type of the attachment"""

    description: str | None = field(
        default=None,
        metadata={"description": "The description of the attachment"},
    )
    """The description of the attachment"""

    uri: str | None = field(
        default=None,
        metadata={
            "description": "The URI of the attachment, if the attachment is a handle",
        },
    )
    """The URI of the attachment, if the attachment is a handle"""

    base64_data: str | None = field(
        default=None,
        metadata={
            "description": "The base64 encoded data of the attachment, if the "
                "attachment is a file",
        },
    )
    """The base64 encoded data of the attachment, if the attachment is a file"""

    kind: Literal["attachment"] = field(
        default="attachment",
        metadata={"description": "Content kind: always 'attachment'"},
        init=False,
    )
    """Content kind: always 'attachment'"""

    @property
    def is_handle(self) -> bool:
        """Whether the attachment is a handle (e.g. a URL)."""
        return self.uri is not None

    def __post_init__(self) -> None:
        """Validates the content type and attachment content after initialization.

        Raises:
            AssertionError: If the kind field doesn't match the literal "attachment".
            ValueError: If the attachment_uri field is empty (attachment is a handle),
                or if the base64_data field is empty (attachment is NOT a handle),
                or if the base64_data field holds invalid base64 data.
        """
        assert_literal_value_valid(self, "kind")

        # Ensure the mime_type is valid
        if not self.mime_type:
            raise ValueError("MIME type cannot be empty")

        if self.is_handle:
            if not self.uri:
                raise ValueError(
                    "Attachment URI cannot be empty if the attachment is a handle",
                )
        else:
            from base64 import b64decode

            if not self.base64_data:
                raise ValueError(
                    "Base64 data cannot be empty if the attachment is NOT a handle",
                )
            try:
                b64decode(self.base64_data)
            except Exception as e:
                raise ValueError("Base64 data is not valid") from e

    def as_text_content(self) -> str:
        """Converts the attachment content to a text content component."""

        description_attr = (
            f'description="{self.description}"' if self.description else ""
        )
        uri_attr = f'uri="{self.uri}"' if self.uri else ""

        return (
            f'<attachment name="{self.name}" mime_type="{self.mime_type}" '
            f"{description_attr} "
            f"{uri_attr} "
            f"/>"
        )

    def model_dump_json(self) -> dict:
        """Serializes the attachment content to a dictionary.
        Useful for JSON serialization."""
        return {
            **super().model_dump_json(),
            "name": self.name,
            "mime_type": self.mime_type,
            "description": self.description,
            "uri": self.uri,
            "base64_data": self.base64_data,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadAttachmentContent":
        """Create a thread attachment content from a dictionary."""
        return cls(**data)


ThreadMessageContent.register_content_kind("attachment", ThreadAttachmentContent)
