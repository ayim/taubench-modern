from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.prompts.content.audio import PromptAudioContent
from agent_platform.core.prompts.content.base import PromptMessageContent
from agent_platform.core.prompts.content.document import PromptDocumentContent
from agent_platform.core.prompts.content.image import PromptImageContent
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PromptToolResultContent(PromptMessageContent):
    """Represents the result of a tool execution in the agent system.

    This class encapsulates the output from a tool execution, which can include
    text and image content, along with status information about the execution.
    """

    tool_name: str = field(
        metadata={"description": "Name of the tool that produced this result"},
    )
    """Name of the tool that produced this result"""

    tool_call_id: str = field(
        metadata={
            "description": "Identifier linking this result to its original tool call",
        },
    )
    """Identifier linking this result to its original tool call"""

    content: list[
        PromptTextContent | PromptImageContent | PromptAudioContent | PromptDocumentContent
    ] = field(
        metadata={
            "description": "List of content items produced by the tool execution",
        },
    )
    """List of content items (text or images) produced by the tool execution"""

    is_error: bool = field(
        default=False,
        metadata={
            "description": "Indicates whether the tool execution resulted in an error",
        },
    )
    """Indicates whether the tool execution resulted in an error"""

    kind: Literal["tool_result"] = field(
        default="tool_result",
        metadata={"description": "Message kind identifier, always 'tool_result'"},
        init=False,
    )
    """Message kind identifier, always 'tool_result'"""

    def __post_init__(self) -> None:
        """Validates the message type after initialization.

        Raises:
            AssertionError: If the kind field doesn't match the literal "tool_result".
        """
        assert_literal_value_valid(self, "kind")

        # TODO: any content validation? It could be anything
        # really (even empty)

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "content": [item.model_dump() for item in self.content],
            "is_error": self.is_error,
        }

    def count_tokens_approx(self) -> int:
        """Counts the approximate number of tokens in the tool result content.

        This method sums the token counts of all content items in the tool result.
        """
        return sum(item.count_tokens_approx() for item in self.content)

    @classmethod
    def model_validate(cls, data: dict) -> "PromptToolResultContent":
        """Create a tool result content from a dictionary."""
        data = data.copy()
        if "content" in data:
            data["content"] = [
                PromptMessageContent.model_validate(item) for item in data["content"]
            ]
        return cls(**data)


# Register this content type with the base class
PromptMessageContent.register_content_kind("tool_result", PromptToolResultContent)
