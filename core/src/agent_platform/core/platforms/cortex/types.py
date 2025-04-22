from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class CortexPromptToolSpec:
    """A tool spec for the Cortex prompt."""

    name: str = field(
        metadata={
            "description": "The name of the tool.",
        },
    )
    """The name of the tool."""

    description: str = field(
        default="",
        metadata={
            "description": "The description of the tool.",
        },
    )
    """The description of the tool."""

    input_schema: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": "The input schema for the tool.",
        },
    )
    """The input schema for the tool."""

    type: Literal["generic"] = field(
        default="generic",
        metadata={
            "description": "The type of tool.",
        },
    )
    """The type of tool."""

    def model_dump(self) -> dict:
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True)
class CortexPromptToolUse:
    """A tool use for the Cortex prompt."""

    tool_use_id: str = field(
        metadata={
            "description": "The ID of the tool use that this tool results are for.",
        },
    )
    """The ID of the tool use that this tool results are for."""

    name: str = field(
        metadata={
            "description": "The name of the tool that generated the results.",
        },
    )
    """The name of the tool that generated the results."""

    input: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": "The input to the tool.",
        },
    )
    """The input to the tool."""

    def model_dump(self) -> dict:
        return {
            "tool_use_id": self.tool_use_id,
            "name": self.name,
            "input": self.input,
        }


@dataclass(frozen=True)
class CortexPromptToolResults:
    """A tool results for the Cortex prompt."""

    tool_use_id: str = field(
        metadata={
            "description": "The ID of the tool use that this tool results are for.",
        },
    )
    """The ID of the tool use that this tool results are for."""

    name: str = field(
        metadata={
            "description": "The name of the tool that generated the results.",
        },
    )
    """The name of the tool that generated the results."""

    content: list["CortexPromptContent"] = field(
        default_factory=list,
        metadata={
            "description": "The content of the tool results.",
        },
    )
    """The content of the tool results."""

    def model_dump(self) -> dict:
        return {
            "tool_use_id": self.tool_use_id,
            "name": self.name,
            "content": [content.model_dump() for content in self.content],
        }


@dataclass(frozen=True)
class CortexPromptContent:
    """A content block for the Cortex prompt."""

    type: Literal["text", "tool_use", "tool_results"] = field(
        default="text",
        metadata={
            "description": "The type of content block.",
        },
    )
    """The type of content block."""

    text: str | None = field(
        default=None,
        metadata={
            "description": "The text content of the content block.",
        },
    )
    """The text content of the content block."""

    tool_use: CortexPromptToolUse | None = field(
        default=None,
        metadata={
            "description": "The tool use for the content block.",
        },
    )
    """The tool use for the content block."""

    tool_results: CortexPromptToolResults | None = field(
        default=None,
        metadata={
            "description": "The tool results for the content block.",
        },
    )
    """The tool results for the content block."""

    def __post_init__(self) -> None:  # noqa: C901
        if self.type == "text":
            if self.text is None:
                raise ValueError(
                    "text must be provided for text content blocks",
                )
            if self.tool_use is not None:
                raise ValueError(
                    "tool_use must be None for text content blocks",
                )
            if self.tool_results is not None:
                raise ValueError(
                    "tool_results must be None for text content blocks",
                )
        elif self.type == "tool_use":
            if self.tool_use is None:
                raise ValueError(
                    "tool_use must be provided for tool use content blocks",
                )
            if self.text is not None:
                raise ValueError(
                    "text must be None for tool use content blocks",
                )
            if self.tool_results is not None:
                raise ValueError(
                    "tool_results must be None for tool use content blocks",
                )
        elif self.type == "tool_results":
            if self.tool_results is None:
                raise ValueError(
                    "tool_results must be provided for tool results content blocks",
                )
            if self.text is not None:
                raise ValueError(
                    "text must be None for tool results content blocks",
                )
            if self.tool_use is not None:
                raise ValueError(
                    "tool_use must be None for tool results content blocks",
                )

    def model_dump(self) -> dict:
        initial_dict: dict[str, Any] = {
            "type": self.type,
        }

        if self.text is not None:
            initial_dict["text"] = self.text
        if self.tool_use is not None:
            initial_dict["tool_use"] = self.tool_use.model_dump()
        if self.tool_results is not None:
            initial_dict["tool_results"] = self.tool_results.model_dump()

        return initial_dict


@dataclass(frozen=True)
class CortexPromptMessage:
    """A message for the Cortex prompt."""

    role: Literal["user", "assistant", "system"] = field(
        default="user",
        metadata={
            "description": "The role of the message.",
        },
    )
    """The role of the message."""

    content: str = field(
        default="",
        metadata={
            "description": "The text content of the message.",
        },
    )
    """The text content of the message."""

    content_list: list[CortexPromptContent] | None = field(
        default=None,
        metadata={
            "description": "The list of content blocks for the message."
            "This most commonly contains tool use or tool results.",
        },
    )
    """The list of content blocks for the message."""

    def model_dump(self) -> dict:
        final_result: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.content_list:
            final_result["content_list"] = [
                content.model_dump() for content in self.content_list
            ]
        return final_result
