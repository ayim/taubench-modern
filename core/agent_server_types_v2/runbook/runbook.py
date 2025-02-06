from dataclasses import dataclass, field
from typing import Self

from agent_server_types_v2.runbook.content import (
    RunbookStepsContent,
    RunbookTextContent,
)


@dataclass
class Runbook:
    """This class represents a runbook, which is textual specification of how an agent should operate."""

    raw_text: str = field(
        metadata={
            "description": "The raw text of the runbook",
        },
    )
    """The raw text of the runbook"""

    # There is some dynamic validation here, we can only have up to
    # ONE steps content; any number of text content components are
    # allowed. By default, we'll make this an empty list.
    content: list[RunbookTextContent | RunbookStepsContent] = field(
        default_factory=list,
        metadata={
            "description": "The content of the runbook",
        },
    )
    """The content of the runbook"""

    def copy(self) -> Self:
        """Returns a deep copy of the runbook."""
        return Runbook(
            raw_text=self.raw_text,
            content=[content.copy() for content in self.content],
        )

    def to_json_dict(self) -> dict:
        """Serializes the runbook to a dictionary. Useful for JSON serialization."""
        return {
            "raw_text": self.raw_text,
            "content": [content.to_json_dict() for content in self.content],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Runbook":
        """Create a runbook from a dictionary."""
        data = data.copy()
        content = [
            RunbookTextContent.from_dict(content) for content in data.pop("content", [])
        ]
        return cls(**data, content=content)
