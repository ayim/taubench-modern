import json
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent
from agent_server_types_v2.thread.content.tool_usage import ThreadToolUsageContent
from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptToolUseContent(PromptMessageContent):
    """Represents a message containing a tool use request from an AI agent.

    This class handles tool usage requests from different LLM providers
    (OpenAI, Claude), normalizing their different input formats into a
    consistent structure.

    Raises:
        json.JSONDecodeError: If tool_input_raw is a string and cannot be
        parsed as valid JSON.
        AssertionError: If type field doesn't match the literal "tool_use".
    """

    tool_call_id: str = field(
        metadata={"description": "Unique identifier for this tool call"},
    )
    """Unique identifier for this tool call"""

    tool_name: str = field(
        metadata={"description": "Name of the tool being requested"},
    )
    """Name of the tool being requested"""

    tool_input_raw: dict[str, Any] | str = field(
        metadata={
            "description": "Raw tool input, either JSON string "
            "(OpenAI) or dict (Claude)",
        },
    )
    """Raw tool input, either JSON string (OpenAI) or dict (Claude)"""

    _tool_input: dict[str, Any] = field(
        init=False,
        metadata={"description": "Parsed tool input parameters as a dictionary"},
    )
    """Parsed tool input parameters as a dictionary"""

    kind: Literal["tool_use"] = field(
        default="tool_use",
        init=False,
        metadata={"description": "Message kind identifier, always 'tool_use'"},
    )
    """Message kind identifier, always 'tool_use'"""

    def __post_init__(self) -> None:
        """Validates and processes the tool input after initialization.

        Ensures the kind field is valid and converts string inputs to dictionaries.
        """
        assert_literal_value_valid(self, "kind")

        if isinstance(self.tool_input_raw, str):
            # Need to use setattr in a frozen dataclass
            # so we can't use the property here
            object.__setattr__(self, "_tool_input", json.loads(self.tool_input_raw))
        else:
            object.__setattr__(self, "_tool_input", self.tool_input_raw)

    @property
    def tool_input(self) -> dict[str, Any]:
        """Returns the tool input as a dictionary.

        This property ensures that the tool input is always a dictionary,
        even if it was originally provided as a string.
        """
        return self._tool_input

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "tool_input_raw": self.tool_input_raw,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "PromptToolUseContent":
        """Create a tool use content from a dictionary."""
        data = data.copy()
        return cls(**data)

    @classmethod
    def from_thread_tool_usage(
        cls,
        thread_tool_usage: ThreadToolUsageContent,
    ) -> "PromptToolUseContent":
        """Create a tool use content from a thread tool usage content."""
        return cls(
            tool_call_id=thread_tool_usage.tool_call_id,
            tool_name=thread_tool_usage.name,
            tool_input_raw=thread_tool_usage.arguments_raw,
        )


# Register this content type with the base class
PromptMessageContent.register_content_kind("tool_use", PromptToolUseContent)
