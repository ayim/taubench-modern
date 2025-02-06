from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.prompts.content.base import PromptMessageContent
from agent_server_types_v2.prompts.content.image import PromptImageContent
from agent_server_types_v2.prompts.content.text import PromptTextContent
from agent_server_types_v2.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptToolResultContent(PromptMessageContent):
    """Represents the result of a tool execution in the agent system.

    This class encapsulates the output from a tool execution, which can include
    text and image content, along with status information about the execution.
    """

    tool_name: str = field(metadata={"description": "Name of the tool that produced this result"})
    """Name of the tool that produced this result"""

    tool_call_id: str = field(metadata={"description": "Identifier linking this result to its original tool call"})
    """Identifier linking this result to its original tool call"""

    content: list[PromptTextContent | PromptImageContent] = field(
        metadata={"description": "List of content items produced by the tool execution"},
    )
    """List of content items (text or images) produced by the tool execution"""

    is_error: bool = field(
        default=False, metadata={"description": "Indicates whether the tool execution resulted in an error"},
    )
    """Indicates whether the tool execution resulted in an error"""

    type: Literal["tool_result"] = field(
        default="tool_result", metadata={"description": "Message type identifier, always 'tool_result'"},
    )
    """Message type identifier, always 'tool_result'"""

    def __post_init__(self) -> None:
        """Validates the message type after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "tool_result".
        """
        assert_literal_value_valid(self, "type")

        # TODO: any content validation? It could be anything
        # really (even empty)