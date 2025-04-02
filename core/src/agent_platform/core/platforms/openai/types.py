import json
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class OpenAIPromptToolSpec:
    """A tool spec for the OpenAI prompt."""

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

    type: Literal["function"] = field(
        default="function",
        metadata={
            "description": "The type of tool.",
        },
    )
    """The type of tool."""

    def model_dump(self) -> dict:
        return {
            "type": self.type,
            "function": {  # Nest these under "function"
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,  # Rename to parameters
            },
        }


@dataclass(frozen=True)
class OpenAIPromptToolUse:
    """A tool use for the OpenAI prompt."""

    tool_use_id: str = field(
        metadata={
            "description": "The ID of the tool use.",
        },
    )
    """The ID of the tool use."""

    name: str = field(
        metadata={
            "description": "The name of the tool.",
        },
    )
    """The name of the tool."""

    input: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": "The input for the tool.",
        },
    )
    """The input for the tool."""

    def model_dump(self) -> dict:
        return {
            "tool_use_id": self.tool_use_id,
            "name": self.name,
            "input": self.input,
        }


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

    def model_dump(self) -> dict:
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

    tool_use: OpenAIPromptToolUse | None = field(
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

    def model_dump(self) -> dict:
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
                    "name": self.tool_use.name,
                    "arguments": json.dumps(
                        self.tool_use.input,
                    ),  # Must be a JSON string
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


@dataclass(frozen=True)
class OpenAIPromptMessage:
    """A message for the OpenAI prompt."""

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
            "description": "The content of the message.",
        },
    )
    """The content of the message."""

    content_list: list[OpenAIPromptContent] | None = field(
        default=None,
        metadata={
            "description": "The list of content blocks for the message.",
        },
    )
    """The list of content blocks for the message."""

    def model_dump(self) -> dict:
        """Convert the message to a dictionary format expected by OpenAI API.

        Returns:
            A dictionary representation of the message.
        """
        # Special case: If this is a user message with tool results, convert it to
        # a tool message
        if (
            self.role == "user"
            and self.content_list
            and any(
                c.type == "tool_results" and c.tool_results for c in self.content_list
            )
        ):
            for content in self.content_list:
                if content.type == "tool_results" and content.tool_results:
                    # Extract the text content from tool results
                    result_text = ""
                    for result_content in content.tool_results.content:
                        if result_content.type == "text" and result_content.text:
                            result_text = result_content.text
                            break

                    # Create a tool message instead of a user message
                    return {
                        # This is the key change - use role "tool" not "user"
                        "role": "tool",
                        "tool_call_id": content.tool_results.tool_use_id,
                        "content": result_text,  # The tool result as a string
                    }

        # Regular case: Assistant with tool calls or normal messages
        result: dict[str, Any] = {"role": self.role}

        # Handle content list - special processing for tool calls
        if self.content_list:
            # Extract tool use content (if any)
            tool_calls = []
            has_tool_calls = False
            text_content = []

            for content in self.content_list:
                if content.type == "text" and content.text:
                    text_content.append(content.text)
                elif content.type == "tool_use" and content.tool_use:
                    has_tool_calls = True
                    # Format tool call according to OpenAI's expected structure
                    tool_calls.append(
                        {
                            "id": content.tool_use.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": content.tool_use.name,
                                "arguments": json.dumps(content.tool_use.input),
                            },
                        },
                    )

            # If it's an assistant message with tool calls
            if self.role == "assistant" and has_tool_calls:
                # For assistant with tool calls, content is null
                if tool_calls:
                    result["tool_calls"] = tool_calls
                # Set content to empty string rather than None to avoid type issues
                result["content"] = ""
            else:
                # Otherwise use joined text content
                result["content"] = "\n".join(text_content) if text_content else ""
        else:
            # Simple string content
            result["content"] = self.content

        return result
