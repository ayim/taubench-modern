import json
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent
from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptToolUseContent(PromptMessageContent):
    """Represents a message containing a tool use request from an AI agent.

    This class handles tool usage requests from different LLM providers (OpenAI, Claude),
    normalizing their different input formats into a consistent structure.

    Raises:
        json.JSONDecodeError: If tool_input_raw is a string and cannot be parsed as valid JSON.
        AssertionError: If type field doesn't match the literal "tool_use".
    """

    tool_call_id: str = field(metadata={"description": "Unique identifier for this tool call"})
    """Unique identifier for this tool call"""

    tool_name: str = field(metadata={"description": "Name of the tool being requested"})
    """Name of the tool being requested"""

    tool_input_raw: dict[str, Any] | str = field(
        metadata={"description": "Raw tool input, either JSON string (OpenAI) or dict (Claude)"},
    )
    """Raw tool input, either JSON string (OpenAI) or dict (Claude)"""

    _tool_input: dict[str, Any] = field(
        init=False, metadata={"description": "Parsed tool input parameters as a dictionary"},
    )
    """Parsed tool input parameters as a dictionary"""

    type: Literal["tool_use"] = field(
        default="tool_use", metadata={"description": "Message type identifier, always 'tool_use'"},
    )
    """Message type identifier, always 'tool_use'"""

    def __post_init__(self) -> None:
        """Validates and processes the tool input after initialization.

        Ensures the type field is valid and converts string inputs to dictionaries.
        """
        assert_literal_value_valid(self, "type")

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