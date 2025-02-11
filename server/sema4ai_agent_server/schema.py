from typing import Annotated, List, Literal, Self, TypedDict

from agent_server_types import Agent, Thread, UploadedFile, User
from anthropic import APIError as AnthropiAPIError
from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile
from langchain_core.runnables import RunnableConfig
from openai import APIError as OpenaiAPIError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    field_serializer,
)
from pydantic_core import ErrorDetails
from sse_starlette.sse import ServerSentEvent

from sema4ai_agent_server.message_types import AnyNonChunkStreamedMessage


class UploadFileRequest(BaseModel):
    file: UploadFile
    embedded: bool | None = Field(
        default=None,
        description="Whether the file is embedded. If None, it will be inferred "
        "from file type.",
    )


class StreamMetadata(BaseModel):
    """
    Metadata emitted by the agent server when streaming a chat request.
    """

    run_id: str = Field(description="The run ID.")


StreamDataType = list[AnyNonChunkStreamedMessage]
StreamDataAdapter = TypeAdapter(StreamDataType)


class StreamErrorData(BaseModel):
    """
    Error data emitted by the agent server when streaming a chat request.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status_code: int = Field(description="The status code associated with the error.")
    message: str | list[ErrorDetails] = Field(description="The error message.")
    _exception: Exception = PrivateAttr()

    @field_serializer("message", mode="wrap")
    def serialize_message(
        self, message: str | list[ErrorDetails], nxt: SerializerFunctionWrapHandler
    ) -> str | list[str]:
        try:
            return nxt(message)
        except Exception:
            if isinstance(message, list):
                return [self._safe_serialize_error_detail(err) for err in message]
            else:
                return message

    def _safe_serialize_error_detail(
        self, error_detail: ErrorDetails
    ) -> dict[str, str]:
        return {
            "loc": error_detail.get("loc"),
            "msg": error_detail.get("msg"),
            "type": error_detail.get("type"),
            "input": repr(error_detail.get("input", None)),
            "ctx": repr(error_detail.get("ctx", None)),
        }

    @classmethod
    def from_error(cls, error: Exception) -> Self:
        """Converts the provided exception into a StreamErrorData instance."""
        # TODO: Expand on for future custom error handling for custom graphs. Future custom
        # error types should be unified across the server and include attributes related
        # to the current provider, model, and other relevant information, as well as
        # allow for control of what is provided to the client/user.
        if isinstance(
            error,
            (OpenaiAPIError, AnthropiAPIError, Boto3Error, BotoCoreError, ClientError),
        ):
            try:
                if isinstance(error, OpenaiAPIError):
                    return cls(
                        status_code=getattr(error, "status_code", 500),
                        message=f"Stream failed due to model API error: {error.message}",
                        _exception=error,
                    )
                if isinstance(error, AnthropiAPIError):
                    return cls(
                        status_code=getattr(error, "status_code", 500),
                        message=f"Stream failed due to model API error: {error.message}",
                        _exception=error,
                    )
                if isinstance(error, Boto3Error):
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
                if isinstance(error, BotoCoreError):
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
                if isinstance(error, ClientError):
                    if "Input is too long" in str(error):
                        return cls(
                            status_code=400,
                            message=f"Stream failed due to model API error: {str(error)}",
                            _exception=error,
                        )
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
            except Exception:
                # TODO: This might leak too much info
                return cls(status_code=500, message=str(error), _exception=error)
        if isinstance(error, ValidationError):
            return cls(
                status_code=500,
                message=error.errors(include_url=False),
                _exception=error,
            )
        return cls(status_code=500, message="Internal server error.", _exception=error)


class BaseStreamEvent(BaseModel):
    """
    A stream event emitted by the agent server when streaming a
    chat request.
    """

    event: Literal["metadata", "data", "error", "end"] = Field(
        description="The event type."
    )
    data: StreamMetadata | StreamDataType | StreamErrorData | None = Field(
        description="The event data."
    )

    def to_sse(self) -> ServerSentEvent:
        """
        Converts the stream event into a ServerSentEvent instance.
        """
        if self.event == "data":
            data = StreamDataAdapter.dump_json(self.data).decode()
        elif self.event != "end":
            data = self.data.model_dump_json()
        else:
            data = None
        return ServerSentEvent(data=data, event=self.event)


class StreamMetadataEvent(BaseStreamEvent):
    event: Literal["metadata"] = "metadata"
    data: StreamMetadata


class StreamDataEvent(BaseStreamEvent):
    event: Literal["data"] = "data"
    data: StreamDataType


class StreamErrorEvent(BaseStreamEvent):
    event: Literal["error"] = "error"
    data: StreamErrorData


class StreamEndEvent(BaseStreamEvent):
    event: Literal["end"] = "end"
    data: None = None


AgentStreamEvent = Annotated[
    StreamMetadataEvent | StreamDataEvent | StreamErrorEvent | StreamEndEvent,
    Field(discriminator="event"),
]
AgentStreamEventAdapter = TypeAdapter(AgentStreamEvent)


class AgentServerRunnableConfigurable(TypedDict):
    """Configurable data used by the agent server when invoking runnables
    compiled from the AgentFactory.
    """

    agent: Agent
    """The agent to use."""

    thread: Thread
    """The thread the agent should be called on."""

    user: User
    """The user associated with the agent."""

    use_retrieval: bool
    """Whether to use retrieval tools."""

    interrupt_before_action: bool
    """Whether to interrupt before actions are called to allow for user review."""

    knowledge_files: List[UploadedFile]
    """Knowledge files available to the agent."""


class AgentServerRunnableConfig(RunnableConfig):
    """Standard runnable config used by the agent server when invoking runnables
    compiled from the AgentFactory.
    """

    configurable: AgentServerRunnableConfigurable
