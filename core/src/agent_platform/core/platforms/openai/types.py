"""Custom content types for OpenAI implementation.

This module contains custom content type classes that haven't been migrated to
use OpenAI SDK types yet.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from openai.types.chat import ChatCompletionMessageToolCall


@dataclass(frozen=True)
class OpenAIPromptToolResults:
    """A tool results for the OpenAI prompt."""

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

    content: list["OpenAIPromptContent"] = field(
        default_factory=list,
        metadata={
            "description": "The content of the tool results.",
        },
    )
    """The content of the tool results."""

    def model_dump(self) -> dict[str, Any]:
        return {
            "tool_use_id": self.tool_use_id,
            "name": self.name,
            "content": [content.model_dump() for content in self.content],
        }


@dataclass(frozen=True)
class OpenAIPromptContent:
    """A content block for the OpenAI prompt."""

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

    tool_use: ChatCompletionMessageToolCall | None = field(
        default=None,
        metadata={
            "description": "The tool use for the content block.",
        },
    )
    """The tool use for the content block."""

    tool_results: OpenAIPromptToolResults | None = field(
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

    def model_dump(self) -> dict[str, Any]:
        """Convert the content block to a dictionary format expected by OpenAI API.

        Returns:
            A dictionary representation of the content block.
        """
        if self.type == "text" and self.text is not None:
            return {
                "type": "text",
                "text": self.text,
            }
        elif self.type == "tool_use" and self.tool_use is not None:
            return {
                "type": "function",  # OpenAI uses "function" instead of "tool_use"
                "function": {
                    "name": self.tool_use.function.name,
                    "arguments": self.tool_use.function.arguments,
                },
            }
        elif self.type == "tool_results" and self.tool_results is not None:
            return {
                "type": "tool_result",
                "tool_call_id": self.tool_results.tool_use_id,
                "content": [
                    content.model_dump() for content in self.tool_results.content
                ],
            }
        else:
            raise ValueError(f"Cannot serialize content with type {self.type}")
