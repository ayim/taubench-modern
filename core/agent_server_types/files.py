from datetime import datetime
from enum import StrEnum
from typing import List

from pydantic import BaseModel, Field, TypeAdapter

from agent_server_types.annotated import StrWithUuidInput


class EmbeddingStatus(StrEnum):
    """
    Enum for embedding status.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"


class UploadedFile(BaseModel):
    file_id: StrWithUuidInput = Field(description="The ID of the file.")
    file_path: str | None = Field(None, description="The path of the file.")
    file_ref: str = Field(description="Key for the file access.")
    file_hash: str = Field(description="The hash of the file.")
    embedded: bool = Field(description="Whether the file is embedded.")
    file_path_expiration: datetime | None = Field(
        default=None,
        description="The expiration date of the file path.",
    )
    embedding_status: EmbeddingStatus | None = Field(
        None, description="The embedding status of the file."
    )
    agent_id: StrWithUuidInput | None = Field(
        default=None,
        description="The ID of the agent that uploaded the file.",
    )
    thread_id: StrWithUuidInput | None = Field(
        default=None,
        description="The ID of the thread that uploaded the file.",
    )


UPLOADED_FILE_LIST_ADAPTER = TypeAdapter(List[UploadedFile])
