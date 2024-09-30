from typing import (
    Any,
    AsyncGenerator,
    Literal,
)

import orjson
import structlog
from langchain_core.messages import (
    AIMessageChunk,
    ToolCall,
)
from pydantic import (
    BaseModel,
    PrivateAttr,
    computed_field,
)
from typing_extensions import TypedDict

FieldStreamerYieldType = AIMessageChunk | None
FieldStreamerSendType = tuple[ToolCall | None, AIMessageChunk]
FieldStreamerType = AsyncGenerator[FieldStreamerYieldType, FieldStreamerSendType | None]

STOP_METADATA = {
    "finish_reason": "stop",
}


class StopStreamerLoop(Exception):
    """Raised when the field streamer should stop."""


class _StreamerMetadata(TypedDict):
    """Metadata for the streamer."""

    reasoning: bool | None
    streamed_from_field: str
    associated_reasoning: str | None


class StreamerMetadata(TypedDict):
    """Metadata for the streamer."""

    sema4ai_metadata: _StreamerMetadata


class FieldStreamerContext(BaseModel):
    """The context passed between field streamer components."""

    # Initial context
    message_id: str
    field_key: str
    field_destination: Literal["message", "reasoning"] = "message"
    field_type: Literal["string", "json"] = "string"
    associated_reasoning: str | None = None

    # Runtime context
    last_sent_type: Literal["metadata", "content", "stop", "none"] = "none"
    received_values: FieldStreamerSendType | None = None
    new_part: str = ""

    # Message context
    tool_call: ToolCall | None = None
    ai_message_chunk: AIMessageChunk | None = None
    metadata: StreamerMetadata = {}

    _logger: structlog.stdlib.BoundLogger = PrivateAttr()

    def model_post_init(self, ctx: Any) -> None:
        self._logger = structlog.get_logger(
            f"{__name__}.FieldStreamer.{self.field_key}"
        )
        self._logger.debug("Initializing field streamer")
        if self.field_destination == "reasoning":
            self.metadata = {
                "sema4ai_metadata": {
                    "reasoning": True,
                    "streamed_from_field": self.field_key,
                }
            }
        elif self.associated_reasoning is not None:
            self.metadata = {
                "sema4ai_metadata": {
                    "associated_reasoning": f"{self.associated_reasoning}_{self.message_id}",
                    "streamed_from_field": self.field_key,
                }
            }
        else:
            self.metadata = {
                "sema4ai_metadata": {
                    "streamed_from_field": self.field_key,
                }
            }
        self._logger.debug(f"Initialized field streamer for key '{self.field_key}'")

    @computed_field
    @property
    def field_msg_id(self) -> str:
        return f"{self.message_id}_{self.field_key}"

    @computed_field
    @property
    def tool_call_field_value(self) -> str | None:
        if self.tool_call is None:
            return None
        return self.tool_call["args"].get(self.field_key, None)  # performance hit?


class StringFieldStreamerContext(FieldStreamerContext):
    """The context passed between field streamer components for a string field."""

    field_type: Literal["string"] = "string"
    previous_length: int = 0

    @computed_field
    @property
    def stringy_field_value(self) -> str:
        return str(self.tool_call_field_value)


class JsonFieldStreamerContext(FieldStreamerContext):
    """The context passed between field streamer components for a json field."""

    field_type: Literal["json"] = "json"
    full_content: str = ""
    buffered_content: str = ""

    @computed_field
    @property
    def args_chunk(self) -> str:
        return self.ai_message_chunk.tool_call_chunks[0]["args"]


def parse_received_values(ctx: FieldStreamerContext) -> None:
    """Handles initial messages that generally should return None."""
    if not ctx.received_values or not ctx.received_values[0]:
        # No tool call received, so we need to wait for the next one
        ctx.last_sent_type = "none"
        return
    ctx.tool_call, ctx.ai_message_chunk = ctx.received_values


def should_wait(ctx: FieldStreamerContext) -> bool:
    """Returns True if the streamer is waiting for more values."""
    if not ctx.tool_call:
        # No tool call received, so we need to wait for the next one
        return True
    if ctx.ai_message_chunk.response_metadata.get("finish_reason") == "stop":
        ctx.last_sent_type = "stop"
        raise StopStreamerLoop("Finish reason is stop. Generator exhausted.")
    ctx._logger.debug(f"Tool call field value: '{ctx.tool_call_field_value}'")
    if ctx.tool_call_field_value is None:
        # There is a tool call, but this streamer's field value is not there
        # or the tool call is empty.
        return True
    return False


# String field streamer helper functions
def is_initial_str_chunk(ctx: StringFieldStreamerContext) -> bool:
    """Returns True if the streamer is handling the initial string chunk."""
    return (
        ctx.field_type == "string"
        and ctx.last_sent_type == "none"
        and ctx.tool_call_field_value == ""
    )


def create_str_metadata_chunk(
    ctx: StringFieldStreamerContext,
) -> AIMessageChunk:
    """Creates the initial metadata chunk for a string field."""
    ctx._logger.debug("Creating initial metadata chunk for string field")
    ctx.last_sent_type = "metadata"
    return AIMessageChunk(
        content="",
        response_metadata=ctx.metadata,
        id=ctx.field_msg_id,
    )


def create_str_content_chunk(ctx: StringFieldStreamerContext) -> AIMessageChunk:
    """Creates the content chunk for a string field."""
    ctx._logger.debug("Creating content chunk for string field")
    ctx.new_part = ctx.stringy_field_value[ctx.previous_length :]
    ctx._logger.debug(f"New part: '{ctx.new_part}'")

    if ctx.last_sent_type in ["metadata", "content"] and not ctx.new_part:
        raise StopStreamerLoop("No new content to send, generator exhausted.")
    ctx.previous_length = len(ctx.stringy_field_value)

    ctx.last_sent_type = "content"
    return AIMessageChunk(
        content=ctx.new_part,
        id=ctx.field_msg_id,
    )


# Json field streamer helper functions
def is_initial_json_chunk(ctx: JsonFieldStreamerContext) -> bool:
    """Returns True if the streamer is handling the initial json chunk."""
    return (
        ctx.field_type == "json"
        and ctx.last_sent_type == "none"
        and ctx.tool_call_field_value in [[], {}]
    )


def create_json_metadata_chunk(ctx: JsonFieldStreamerContext) -> AIMessageChunk:
    """Creates the initial metadata chunk for a json field."""
    ctx._logger.debug("Creating initial metadata chunk for json field")
    # buffer first args chunk
    ctx.buffered_content = ctx.args_chunk
    ctx._logger.debug(f"Buffered content: '{ctx.buffered_content}'")
    ctx.last_sent_type = "metadata"
    return AIMessageChunk(
        content="",
        response_metadata=ctx.metadata,
        id=ctx.field_msg_id,
    )


def is_first_content_json_chunk(ctx: JsonFieldStreamerContext) -> bool:
    """Returns True if the streamer is handling the first content json chunk."""
    return (
        ctx.field_type == "json"
        and ctx.last_sent_type == "metadata"
        and ctx.full_content == ""
    )


def parse_first_new_part(ctx: JsonFieldStreamerContext) -> None:
    """Parses the first new part of a json field by finding the first
    opening bracket and starting the new part from there."""
    ctx._logger.debug("Parsing first new part of json field")
    if "{" in ctx.new_part and "[" in ctx.new_part:
        opening_brace_index = min(ctx.new_part.find("{"), ctx.new_part.find("["))
    elif "{" in ctx.new_part:
        opening_brace_index = ctx.new_part.find("{")
    elif "[" in ctx.new_part:
        opening_brace_index = ctx.new_part.find("[")
    else:
        opening_brace_index = -1
    ctx.new_part = (
        ctx.new_part[opening_brace_index:]
        if opening_brace_index != -1
        else ctx.new_part
    )
    ctx.full_content = ctx.new_part


def parse_new_part(ctx: JsonFieldStreamerContext) -> None:
    """Parses a new part and checks for end by attempting to load
    the partial JSON with each character in new part sequentially. If
    it loads, this function will raise StopStreamerLoop."""
    last_message = ""
    for char in ctx.new_part:
        last_message += char
        ctx.full_content += char
        ctx._logger.debug(f"Attempting to parse content: '{ctx.full_content}'")
        try:
            _ = orjson.loads(ctx.full_content)
        except orjson.JSONDecodeError:
            pass
        else:
            ctx.new_part = last_message
            raise StopStreamerLoop("JSON field can be parsed. Generator exhausted.")


def create_json_content_chunk(ctx: JsonFieldStreamerContext) -> AIMessageChunk:
    """Creates a content chunk for a json field."""
    ctx._logger.debug("Creating content chunk for json field")
    is_end = False
    if is_first_content_json_chunk(ctx):
        parse_first_new_part(ctx)
    else:
        try:
            parse_new_part(ctx)
        except StopStreamerLoop:
            is_end = True
    ctx._logger.debug(f"New part: '{ctx.new_part}'")

    if not is_end:
        ctx.last_sent_type = "content"
        return AIMessageChunk(
            content=ctx.new_part,
            id=ctx.field_msg_id,
        )
    else:
        ctx.last_sent_type = "stop"
        return AIMessageChunk(
            content=ctx.new_part,
            response_metadata=STOP_METADATA,
            id=ctx.field_msg_id,
        )


def create_stop_msg(ctx: FieldStreamerContext) -> AIMessageChunk:
    if ctx.last_sent_type not in ["none", "stop"]:
        ctx._logger.debug("Sending stop message.")
        ctx.last_sent_type = "stop"
        return AIMessageChunk(
            content="",
            response_metadata=STOP_METADATA,
            id=ctx.field_msg_id,
        )
    else:
        ctx._logger.debug("No need to send stop message.")


# Main generator function
async def field_streamer(
    message_id: str,
    field_key: str,
    field_destination: Literal["message", "reasoning"],
    field_type: Literal["string", "json"] = "string",
    associated_reasoning: str | None = None,
) -> FieldStreamerType:
    """Asynchronously stream tool call fields to message/reasoning.

    When sending to this generator, you must send a tuple of a combined ToolCall and the
    current message chunk. This is necessary for JSON fields."""

    if field_type == "json":
        ctx = JsonFieldStreamerContext(
            message_id=message_id,
            field_key=field_key,
            field_destination=field_destination,
            associated_reasoning=associated_reasoning,
        )
    else:
        ctx = StringFieldStreamerContext(
            message_id=message_id,
            field_key=field_key,
            field_destination=field_destination,
            associated_reasoning=associated_reasoning,
        )

    ctx.received_values = yield None  # Yield None on successful initialization

    # Main event loop
    try:
        while ctx.last_sent_type != "stop":
            ctx._logger.debug(
                f"Main loop top, received values: '{ctx.received_values}'"
            )
            parse_received_values(ctx)
            if should_wait(ctx):
                ctx.last_sent_type = "none"
                ctx.received_values = yield None
                continue

            elif ctx.field_type == "string":
                if is_initial_str_chunk(ctx):
                    ctx.received_values = yield create_str_metadata_chunk(ctx)
                    continue
                else:
                    ctx.received_values = yield create_str_content_chunk(ctx)
                    continue

            elif ctx.field_type == "json":
                if is_initial_json_chunk(ctx):
                    ctx.received_values = yield create_json_metadata_chunk(ctx)
                    continue
                else:
                    # Prepend any buffered content
                    ctx.new_part = ctx.buffered_content + ctx.args_chunk
                    ctx._logger.debug(f"Unparsed chunk: '{ctx.new_part}'")
                    ctx.buffered_content = ""
                    ctx.received_values = yield create_json_content_chunk(ctx)
                    continue

    except StopStreamerLoop as ex:
        ctx._logger.debug(f"Main loop broken: {ex}")
    finally:
        # Cleanup
        yield create_stop_msg(ctx)
