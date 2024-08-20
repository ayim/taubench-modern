from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class User(BaseModel):
    user_id: str = Field(description="The ID of the user.")
    sub: str = Field(description="The sub of the user (from a JWT token).")
    created_at: datetime = Field(description="The time the user was created.")


class Assistant(BaseModel):
    """Assistant model."""

    assistant_id: str = Field(description="The ID of the assistant.")
    user_id: str = Field(description="The ID of the user that owns the assistant.")
    name: str = Field(description="The name of the assistant.")
    config: dict = Field(description="The assistant config.")
    updated_at: datetime = Field(description="The last time the assistant was updated.")
    public: bool = Field(description="Whether the assistant is public.")
    metadata: Optional[dict] = Field(description="The assistant metadata.")


class Thread(BaseModel):
    thread_id: str = Field(description="The ID of the thread.")
    user_id: str = Field(description="The ID of the user.")
    assistant_id: Optional[str] = Field(description="The ID of the assistant.")
    name: str = Field(description="The name of the thread.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Optional[dict] = Field(description="The thread metadata.")


class UploadedFile(TypedDict):
    file_id: str
    """The ID of the file."""
    file_path: Optional[str]
    """The path of the file."""
    file_ref: str
    """Key for the file access."""
    file_hash: str
    """The hash of the file."""
    embedded: bool
    """Whether the file is embedded."""
