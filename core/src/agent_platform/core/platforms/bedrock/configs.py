from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata


@dataclass(frozen=True)
class BedrockContentLimits(Configuration):
    """Content limits and associated global configurations for the Bedrock platform."""

    max_image_count: int = field(
        default=20,
        metadata=FieldMetadata(
            description="The maximum number of images that can be included in a request.",
        ),
    )
    max_image_size: int = field(
        default=3_750_000,
        metadata=FieldMetadata(
            description="The maximum size of an image in bytes.",
        ),
    )
    max_image_height: int = field(
        default=8_000,
        metadata=FieldMetadata(
            description="The maximum height of an image in pixels.",
        ),
    )
    max_image_width: int = field(
        default=8_000,
        metadata=FieldMetadata(
            description="The maximum width of an image in pixels.",
        ),
    )
    max_document_count: int = field(
        default=5,
        metadata=FieldMetadata(
            description="The maximum number of documents that can be included in a request.",
        ),
    )
    max_document_size: int = field(
        default=4_500_000,
        metadata=FieldMetadata(
            description="The maximum size of a document in bytes.",
        ),
    )


@dataclass(frozen=True)
class BedrockMimeTypeMap(Configuration):
    """A map of Bedrock format types to MIME types supported by the platform."""

    mime_type_map: dict[str, str] = field(
        default_factory=lambda: {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "csv": "text/csv",
            "md": "text/markdown",
            "html": "text/html",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        metadata=FieldMetadata(
            description=("A map of Bedrock format types to MIME types supported by the platform."),
        ),
    )

    @classmethod
    def supported_format_types(cls) -> list[str]:
        """Get list of supported format types."""
        return list(cls.mime_type_map.keys())

    @classmethod
    def reverse_mapping(cls) -> dict[str, str]:
        """Get reverse mapping of MIME types to format types."""
        return {v: k for k, v in cls.mime_type_map.items()}
