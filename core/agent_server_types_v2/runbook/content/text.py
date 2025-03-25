from dataclasses import dataclass, field
from typing import Literal, Self

from agent_server_types_v2.runbook.content import RunbookContent


@dataclass
class RunbookTextContent(RunbookContent):
    """This class represents a simple text content component in a runbook."""

    content: str = field(
        metadata={
            "description": "The content of the text",
        },
    )
    """The content of the text"""

    type: Literal["text"] = field(
        default="text",
        metadata={
            "description": "The type of content",
        },
    )
    """The type of content"""

    def copy(self) -> Self:
        """Returns a deep copy of the runbook text content."""
        return RunbookTextContent(
            content=self.content,
        )

    def model_dump(self) -> dict:
        """Serializes the runbook text content to a dictionary.
        Useful for JSON serialization."""
        return {
            "content": self.content,
            "type": self.type,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookTextContent":
        """Create a runbook text content from a dictionary."""
        return cls(**data)
