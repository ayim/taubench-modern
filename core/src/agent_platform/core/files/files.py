from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from fastapi import UploadFile


@dataclass(frozen=True)
class UploadedFile:
    """Represents an uploaded file."""

    file_id: str
    """The ID of the file."""

    file_path: str | None
    """The path of the file."""

    file_ref: str
    """Key for the file access."""

    file_hash: str
    """The hash of the file."""

    file_size_raw: int
    """The size of the file in bytes."""

    mime_type: str
    """The MIME type of the file."""

    created_at: datetime
    """The date and time the file was created."""

    embedded: bool = False
    """Whether the file is embedded."""

    file_path_expiration: datetime | None = None
    """The expiration date of the file path."""

    agent_id: str | None = None
    """The ID of the agent that uploaded the file."""

    thread_id: str | None = None
    """The ID of the thread that uploaded the file."""

    user_id: str | None = None
    """The ID of the user that uploaded the file."""

    @classmethod
    def model_validate(cls, data: dict) -> "UploadedFile":
        """Create an UploadedFile from a dictionary."""
        data = data.copy()
        if "file_id" in data and isinstance(data["file_id"], UUID):
            data["file_id"] = str(data["file_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        if "file_path_expiration" in data and isinstance(
            data["file_path_expiration"],
            str,
        ):
            data["file_path_expiration"] = datetime.fromisoformat(
                data["file_path_expiration"],
            )
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])

        return cls(**data)


@dataclass(frozen=True)
class UploadFileRequest:
    """Represents a request to upload a file."""

    file: "UploadFile"
    """The file to upload."""

    embedded: bool = False
    """Whether the file is embedded."""


@dataclass(frozen=True)
class FileData:
    """Represents file data."""

    content: bytes
    """The content of the file."""

    file_name: str
    """The name of the file."""

    mime_type: str
    """The MIME type of the file."""

    file_size: int
    """The size of the file in bytes."""

    @classmethod
    def model_validate(cls, data: dict) -> "FileData":
        """Create a FileData from a dictionary."""
        return cls(**data)


@dataclass(frozen=True)
class RemoteFileUploadData:
    """Represents data needed for remote file upload."""

    url: str
    """The URL to upload the file to."""

    form_data: dict
    """Form data required for the upload."""

    file_id: str
    """The ID of the file."""

    file_ref: str
    """The reference name of the file."""

    @classmethod
    def model_validate(cls, data: dict) -> "RemoteFileUploadData":
        """Create a RemoteFileUploadData from a dictionary."""
        return cls(**data)
