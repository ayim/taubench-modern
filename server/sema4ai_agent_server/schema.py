from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    user_id: str = Field(description="The ID of the user.")
    sub: str = Field(description="The sub of the user (from a JWT token).")
    created_at: datetime = Field(description="The time the user was created.")


class Agent(BaseModel):
    """Agent model."""

    id: str = Field(description="The ID of the agent.")
    user_id: str = Field(description="The ID of the user that owns the agent.")
    name: str = Field(description="The name of the agent.")
    config: dict = Field(description="The agent config.")
    updated_at: datetime = Field(description="The last time the agent was updated.")
    public: bool = Field(description="Whether the agent is public.")
    metadata: Optional[dict] = Field(description="The agent metadata.")


class Thread(BaseModel):
    thread_id: str = Field(description="The ID of the thread.")
    user_id: str = Field(description="The ID of the user.")
    agent_id: Optional[str] = Field(description="The ID of the agent.")
    name: str = Field(description="The name of the thread.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Optional[dict] = Field(description="The thread metadata.")


class UploadedFile(BaseModel):
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
    file_path_expiration: Optional[datetime] = None
