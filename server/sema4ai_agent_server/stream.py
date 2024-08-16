from typing import (
    Any,
    AsyncIterator,
    Dict,
    Optional,
    Sequence,
    Union,
)

import orjson
import structlog
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    BaseMessageChunk,
    ToolCall,
    message_chunk_to_message,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langserve.serialization import WellKnownLCSerializer
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
)

from sema4ai_agent_server.message_types import ToolEventMessage
from sema4ai_agent_server.structured_response_streamer import (
    StructuredResponseStreamerType,
    structured_response_streamer,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

MessagesStream = AsyncIterator[Union[list[AnyMessage], str]]


async def invoke_state(
    app: Runnable,
    input: Union[Sequence[AnyMessage], Dict[str, Any]],
    config: RunnableConfig,
) -> MessagesStream:
    """Return messages from the runnable."""
    return await app.ainvoke(input, config)


async def astream_state(
    app: Runnable,
    input: Union[Sequence[AnyMessage], Dict[str, Any]],
    config: RunnableConfig,
) -> MessagesStream:
    """Stream messages from the runnable."""
    root_run_id: Optional[str] = None
    messages: dict[str, BaseMessage] = {}
    tool_calls: list[ToolCall] = []
    """List of tool calls to match with tool start events."""
    struct_streamer: StructuredResponseStreamerType | None = None

    async for event in app.astream_events(
        input, config, version="v1", stream_mode="values", exclude_tags=["nostream"]
    ):
        if event["event"] == "on_chain_start" and not root_run_id:
            root_run_id = event["run_id"]
            yield root_run_id
        elif event["event"] == "on_chain_stream" and event["run_id"] == root_run_id:
            new_messages: list[BaseMessage] = []

            # event["data"]["chunk"] is a Sequence[AnyMessage] or a Dict[str, Any]
            state_chunk_msgs: Union[Sequence[AnyMessage], Dict[str, Any]] = event[
                "data"
            ]["chunk"]
            metadata: Dict[str, Dict[str, Any]] = {
                "sema4ai_metadata": event.get("metadata", {})
            }
            if isinstance(state_chunk_msgs, dict):
                logger.debug(
                    f"astream_state:on_chain_stream:state_chunk_msgs: {state_chunk_msgs}"
                )
                state_chunk_msgs = event["data"]["chunk"]["messages"]

            for msg in state_chunk_msgs:
                msg_id = msg["id"] if isinstance(msg, dict) else msg.id
                if msg_id in messages and msg == messages[msg_id]:
                    continue
                else:
                    if isinstance(msg, dict):
                        if "response_metadata" not in msg:
                            msg["response_metadata"] = {}
                        msg["response_metadata"].update(metadata)
                    else:
                        msg.response_metadata.update(metadata)
                    # Handle Pydantic Response Models not implemented for chain streams
                    messages[msg_id] = msg
                    new_messages.append(msg)
            if new_messages:
                yield new_messages
        elif event["event"] == "on_chat_model_start":
            # Set up pydantic model response streamer if needed
            logger.debug(
                f"astream_state:on_chat_model_start:metadata: {event['metadata']}"
            )
            structured_response_config = event["metadata"].get(
                "structured_response_config", {}
            )
            if structured_response_config:
                struct_streamer = structured_response_streamer(
                    structured_response_config
                )
                await struct_streamer.asend(None)  # Start the generator
                logger.debug("Pydantic model response streamer set up.")
        elif event["event"] == "on_chat_model_stream":
            message: BaseMessageChunk = event["data"]["chunk"]
            logger.debug(f"astream_state:on_chat_model_stream:new chunk: {message}")

            metadata: Dict[str, Dict[str, Any]] = {
                "sema4ai_metadata": event.get("metadata", {})
            }

            # Handle Structured Responses
            structured_response_config = metadata["sema4ai_metadata"].get(
                "structured_response_config", {}
            )
            if (
                structured_response_config
                and "reasoning" in metadata["sema4ai_metadata"]
            ):
                raise ValueError(
                    "Cannot have reasoning and pydantic_model_response metadata at the same time."
                )
            if structured_response_config and (
                message.tool_call_chunks
                or message.response_metadata.get("finish_reason") == "stop"
            ):
                try:
                    message = await struct_streamer.asend(message)
                except (StopAsyncIteration, StopIteration):
                    pass

            if not message:
                # If the pydantic model response generator set the message to None, we need to skip this event.
                continue

            if message.id not in messages:
                # Attach metadata to new messages
                # TODO: Original metedata isn't coming through because `message` is the new message
                # created by the structured response streamer, not the original.
                if "sema4ai_metadata" in message.response_metadata:
                    # This is the case when there is a pydantic model response
                    message.response_metadata["sema4ai_metadata"].update(
                        metadata["sema4ai_metadata"]
                    )
                    logger.debug(
                        f"astream_state:on_chat_model_stream:structured_response_streamer final metadata: {message.response_metadata}"
                    )
                else:
                    message.response_metadata.update(metadata)
                    logger.debug(
                        f"astream_state:on_chat_model_stream:final metadata: {message.response_metadata}"
                    )
                messages[message.id] = message
            else:
                messages[message.id] += message
                # TODO: Check if this works for other LLMs besides OpenAI.
                if message.response_metadata.get("finish_reason") == "tool_calls":
                    tool_calls = messages[message.id].tool_calls
                else:
                    tool_calls = []
            yield [messages[message.id]]
        elif event["event"] == "on_tool_start":
            # Explicitly send tool start events to the front end
            logger.debug(f"astream_state:on_tool_start:event: {event}")

            for tool_call in tool_calls:
                if tool_call["name"] == event["name"] and all(
                    tool_call["args"].get(k) == v
                    for k, v in event["data"]["input"].items()
                ):
                    tool_call_id = tool_call["id"]
            input_message = ToolEventMessage(
                content="",
                id=event["run_id"],
                tool_call_id=tool_call_id,
                input=event["data"]["input"],
                response_metadata=event.get("metadata", {}),
            )
            logger.debug(f"astream_state:on_tool_start:input_message: {input_message}")

            if input_message.id not in messages:
                messages[input_message.id] = input_message
                yield [input_message]
            else:
                messages[input_message.id] += input_message
                yield [messages[input_message.id]]
        elif event["event"] == "on_tool_end":
            # Explicitly send tool end events to the front end
            logger.debug(f"astream_state:on_tool_end:event: {event}")
            try:
                tool_call_id = messages[event["run_id"]].tool_call_id
            except (KeyError, AttributeError):
                tool_call_id = None
            output_message = ToolEventMessage(
                content="",
                id=event["run_id"],
                tool_call_id=tool_call_id,
                output=event["data"]["output"],
                response_metadata=event.get("metadata", {}),
            )
            logger.debug(f"astream_state:on_tool_end:output_message: {output_message}")

            if output_message.id not in messages:
                messages[output_message.id] = output_message
                yield [output_message]
            else:
                messages[output_message.id] += output_message
                yield [messages[output_message.id]]


_serializer = WellKnownLCSerializer()


def _get_status_code_and_message(e: Exception) -> tuple[int | None, str]:
    status_code, message = 500, "Internal Server Error"
    if isinstance(e, APIStatusError):
        status_code = e.status_code
        message = (
            e.response.json().get("error", {}).get("message", "Something went wrong.")
        )
    elif isinstance(e, APIConnectionError):
        # No connection established, so no status code.
        status_code = None
        message = e.message
    elif isinstance(e, APIResponseValidationError):
        # Validation error by openai-python SDK (instead of OpenAI's API), so no status code.
        status_code = None
        message = e.message
    return status_code, message


async def to_sse(messages_stream: MessagesStream) -> AsyncIterator[dict]:
    """Consume the stream into an EventSourceResponse"""
    try:
        async for chunk in messages_stream:
            # EventSourceResponse expects a string for data
            # so after serializing into bytes, we decode into utf-8
            # to get a string.
            if isinstance(chunk, str):
                yield {
                    "event": "metadata",
                    "data": orjson.dumps({"run_id": chunk}).decode(),
                }
            else:
                yield {
                    "event": "data",
                    "data": _serializer.dumps(
                        [message_chunk_to_message(msg) for msg in chunk]
                    ).decode(),
                }
    except Exception as e:
        logger.warn("error in stream", exc_info=True)
        status_code, message = _get_status_code_and_message(e)
        data = orjson.dumps({"status_code": status_code, "message": message}).decode()
        yield {"event": "error", "data": data}

    # Send an end event to signal the end of the stream
    yield {"event": "end"}
