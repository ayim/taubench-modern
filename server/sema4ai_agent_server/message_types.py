from typing import Any, Literal, get_args

from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    FunctionMessage,
    MessageLikeRepresentation,
    ToolMessage,
    merge_content,
)
from langchain_core.utils._merge import merge_dicts
from langgraph.graph.message import Messages, add_messages
from pydantic import Field


class LiberalFunctionMessage(FunctionMessage):
    content: Any


class LiberalToolMessage(ToolMessage):
    content: Any


def _convert_pydantic_dict_to_message(
    data: MessageLikeRepresentation,
) -> MessageLikeRepresentation:
    if (
        isinstance(data, dict)
        and "content" in data
        and isinstance(data.get("type"), str)
    ):
        for cls in get_args(AnyMessage):
            if data["type"] == cls(content="").type:
                return cls(**data)
    return data


def add_messages_liberal(left: Messages, right: Messages):
    # coerce to list
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    return add_messages(
        [_convert_pydantic_dict_to_message(m) for m in left],
        [_convert_pydantic_dict_to_message(m) for m in right],
    )


class ToolEventMessage(BaseMessage):
    """Messages between the system/caller and a tool. This message may represent either
    a call to a tool or the response, or both. The `run_id` field is used to track
    the tool call and response. The `input` field is used to pass arguments to
    the tool and the output is the response.
    """

    tool_call_id: str | None = None
    """Tool call that this message is responding to."""

    type: Literal["tool_event"] = "tool_event"

    input: dict = Field(default_factory=dict)
    """Input to the tool, which generally represent the arguments passed to the tool."""
    output: Any = None
    """Output of the tool, which generally represents the result of the tool call. This is
    usually a str, dict, list, or other serializable object."""

    def __add__(self, other: "ToolEventMessage") -> "ToolEventMessage":
        if not isinstance(other, ToolEventMessage):
            raise ValueError(
                f"Cannot concatenate ToolEventMessage with {type(other)} object."
            )
        if self.id != other.id:
            raise ValueError("Cannot concatenate ToolEventMessages with different ids.")
        if (
            self.tool_call_id is not None
            and other.tool_call_id is not None
            and self.tool_call_id != other.tool_call_id
        ):
            raise ValueError(
                "Cannot concatenate ToolEventMessages with different tool_call_ids."
            )
        if self.input != {} and other.input != {}:
            raise ValueError(
                "Cannot concatenate ToolEventMessages where both have input."
            )
        else:
            input = self.input or other.input
        if self.output is not None and other.output is not None:
            raise ValueError(
                "Cannot concatenate ToolEventMessages where both have output."
            )
        else:
            output = self.output or other.output
        return self.__class__(
            content=merge_content(self.content, other.content),
            id=self.id,
            tool_call_id=self.tool_call_id or other.tool_call_id,
            input=input,
            output=output,
            additional_kwargs=merge_dicts(
                self.additional_kwargs, other.additional_kwargs
            ),
            response_metadata=merge_dicts(
                self.response_metadata, other.response_metadata
            ),
        )
