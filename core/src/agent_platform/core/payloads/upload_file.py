from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import UploadFile


@dataclass(frozen=True)
class UploadFilePayload:
    file: "UploadFile" = field(
        metadata={
            "description": "The file to upload.",
        },
    )
    """The file to upload."""

    embedded: bool | None = field(
        default=None,
        metadata={
            "description": (
                "Whether the file is embedded. If None, it will be inferred from file type."
            ),
        },
    )
    """Whether the file is embedded. If None, it will be inferred from file type."""
