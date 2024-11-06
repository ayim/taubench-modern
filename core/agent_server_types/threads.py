from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, List

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from agent_server_types.annotated import StrWithUuidInput


class Thread(BaseModel):
    thread_id: StrWithUuidInput = Field(description="The ID of the thread.")
    user_id: StrWithUuidInput = Field(description="The ID of the user.")
    agent_id: StrWithUuidInput | None = Field(None, description="The ID of the agent.")
    name: str = Field(description="The name of the thread.")
    created_at: datetime = Field(description="The time the thread was updated.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Annotated[dict | None, "db_json"] = Field(
        None, description="The thread metadata."
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict | None:
        if isinstance(v, (str, bytes, bytearray)) and v != "null":
            return TypeAdapter(dict).validate_json(v)
        elif v == "null":
            return None
        return v


THREAD_LIST_ADAPTER = TypeAdapter(List[Thread])

# Used to avoid breaking the app as part of agent factory creation
dummy_thread = Thread(
    thread_id="dummy",
    user_id="dummy",
    agent_id="dummy",
    name="dummy",
    created_at=datetime.now(),
    updated_at=datetime.now(),
    metadata={},
)


class ChatRole(StrEnum):
    """
    Enum for chat participant types.
    """

    AI = "ai"
    HUMAN = "human"
    SYSTEM = "system"
    ACTION = "tool"


class ChatMessage(BaseModel):
    """
    Represents a chat message in a thread.
    A chat message can be from the ai, human, system, or action.
    """

    id: StrWithUuidInput | None = Field(
        None, description="The ID of the chat message. This can be a random UUID."
    )
    type: ChatRole = Field(description="The role of the chat message.")
    content: str = Field(description="The message.")
    example: bool = Field(
        description="Whether the message is an example.", default=False
    )


class ChatRequest(BaseModel):
    """
    A request to chat with an Agent Thread.
    """

    input: List[ChatMessage] = Field(description="The messages to send to the agent.")
    thread_id: StrWithUuidInput = Field(description="The ID of the thread.")
