"""This module provides the streaming component with a asynchronous generator
capable of streaming individual fields from a structured response (generally
a Pydantic model or TypedDict) to either the 'message' or 'reasoning'
components of the front end."""

import asyncio
from typing import AsyncGenerator, Sequence, cast

import structlog
from langchain_core.messages import AIMessageChunk, ToolCall

from app.structured_response_streamer.field_streamer import (
    FieldStreamerType,
    StopStreamerLoop,
    field_streamer,
)

StructuredResponseStreamerType = AsyncGenerator[AIMessageChunk | None, AIMessageChunk]


class StopStructuredResponse(Exception):
    """Exception raised when the structured response streamer should be exhausted."""


# Helper functions
async def create_streamers(
    fields: Sequence[tuple[str, str]],
    message_id: str,
) -> list[FieldStreamerType]:
    """Create a set of generators, one for each field provided.

    Args:
        fields: A list of tuples, each containing the field key and the field type
            (e.g., either "message" or "reasoning") as well as optional components of
            the field type and associated reasoning.
        message_id: The message id.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(
        f"{__name__}.create_streamers"
    )
    streamers = []
    for field_key, field_destination, *opts in fields:
        logger.debug(
            f"{field_destination} streamer initializing for {field_key}. Options: {opts}"
        )
        field_type = "string"
        associated_reasoning = None
        if opts:
            field_type = opts[0]
            if len(opts) > 1:
                associated_reasoning = opts[1]
        streamer = field_streamer(
            message_id, field_key, field_destination, field_type, associated_reasoning
        )
        await streamer.asend(None)  # Start the generator
        logger.debug(f"{field_destination} streamer initialized for {field_key}.")
        streamers.append(streamer)
    return streamers


async def gather_streamer_results(
    streamers: Sequence[FieldStreamerType],
    tool_call: ToolCall | None,
    ai_message_chunk: AIMessageChunk,
) -> AIMessageChunk:
    """Gather the results from all streamers and return the updated message chunk."""
    tasks = [streamer.asend((tool_call, ai_message_chunk)) for streamer in streamers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Only one result should be not None or not an exception
    if all(
        isinstance(result, (StopIteration, StopAsyncIteration, StopStreamerLoop))
        for result in results
    ):
        # Raise StopIteration if all generators exhausted.
        raise StopStructuredResponse("All streamers exhausted.")
    for result in results:
        if result is None or isinstance(
            result, (StopIteration, StopAsyncIteration, StopStreamerLoop)
        ):
            continue  # Skip if the result is None or a stop iteration
        if isinstance(result, BaseException):
            raise result  # re-raise exceptions I am not handling
        return result


async def close_streamers(streamers: Sequence[FieldStreamerType]) -> None:
    """Close all streamers."""
    for streamer in streamers:
        try:
            await streamer.aclose()
        except StopAsyncIteration:
            pass


async def structured_response_streamer(
    config: dict[str, str],
) -> StructuredResponseStreamerType:
    """Allows for structured output from an LLM to be streamed to either the messages
    and/or reasoning components in the front end. The LLM must call a Pydantic model or
    TypedDict model with a specific structure. The fields to be streamed
    are defined via metadata in the invocation of the LLM runnable.

    Each streamable field must be defined as a tuple in a list attached to the `fields` key.
    Each tuple must consist of at least two components: the field key and the field destination.
    It may optionally contain a third component, which is the field type and can only be `string`
    or `json`. If `json`, the field will be loaded and then serialized; otherwise, it will be
    streamed as a string. The fourth component is the associated reasoning, which should be the
    field name of the reasoning field that the message field is associated with.

    In the example below, the `plan_needed_response` field will be streamed to the messages
    component in the front end, and the `reasoning` field will be streamed to the reasoning
    component. The `PlanNeededResponse` model is the Pydantic model that the LLM is required
    to call, and this function will only pull fields from that specific tool call in case of
    multiple tool calls.

    When defining the sequence of fields to stream, it's important that any "reasoning" fields
    are defined first, followed by "message" fields. This is because the reasoning field is
    streamed first, and then the message field is streamed. This ensures that the reasoning is
    displayed before the message. The field definition should be consistent with the order of
    the fields in the Pydantic model, as the LLM will generate fields in the order they are defined.

    Example:

    ```python
        plan_needed_response: PlanNeededResponse = agent.with_config(
            {
                "metadata": {
                    "structured_response_config": {
                        "model_name": "PlanNeededResponse",
                        "fields": [
                            ("reasoning", "reasoning"),
                            ("plan_needed_response", "message", "string", "reasoning"),
                            ("steps", "reasoning", "json")
                        ],
                    }
                }
            }
        ).invoke(
            {
                "agent_name": agent_name,
                "datetime": datetime.now().isoformat(),
                "runbook": system_message,
                "messages": messages,
            }
        )
    ```
    """
    fields = config["fields"]
    model_name = config["model_name"]
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(
        f"{__name__}.structured_response_streamer:{model_name}"
    )
    ai_message_chunk = yield None  # Primer yield

    logger.debug(f"First ai_message_chunk: {ai_message_chunk}")
    ai_message = AIMessageChunk(content="", id=ai_message_chunk.id)
    streamers = await create_streamers(fields, ai_message_chunk.id)
    while ai_message_chunk.id == ai_message.id:
        ai_message += ai_message_chunk
        ai_message = cast(AIMessageChunk, ai_message)
        logger.debug(f"ai_message with new chunk: {ai_message}")
        tool_calls = ai_message.tool_calls
        # The first tool call with the provided name is the one we are interested in
        model_tool_call = next(
            (t for t in tool_calls if t.get("name", "") == model_name), None
        )
        logger.debug(f"tool_call: {model_tool_call}")
        try:
            ai_message_chunk = await gather_streamer_results(
                streamers, model_tool_call, ai_message_chunk
            )
            logger.debug(f"outgoing ai_message_chunk: {ai_message_chunk}")
            ai_message_chunk = yield ai_message_chunk
            continue
        except (StopAsyncIteration, StopIteration, StopStreamerLoop):
            logger.debug("Streamer exhausted.")
            ai_message_chunk = yield None
            break
    await close_streamers(streamers)
