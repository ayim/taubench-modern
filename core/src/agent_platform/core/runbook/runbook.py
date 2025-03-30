from dataclasses import dataclass, field
from typing import cast

from agent_platform.core.runbook.content import (
    AnyRunbookContent,
    RunbookContent,
)


@dataclass
class Runbook:
    """This class represents a runbook, which is textual
    specification of how an agent should operate."""

    raw_text: str = field(
        metadata={
            "description": "The raw text of the runbook",
        },
    )
    """The raw text of the runbook"""

    # There is some dynamic validation here, we can only have up to
    # ONE steps content; any number of text content components are
    # allowed. By default, we'll make this an empty list.
    content: list[AnyRunbookContent] = field(
        metadata={
            "description": "The content of the runbook",
        },
    )
    """The content of the runbook"""

    def copy(self) -> "Runbook":
        """Returns a deep copy of the runbook."""
        return Runbook(
            raw_text=self.raw_text,
            content=[content.copy() for content in self.content],
        )

    def model_dump(self) -> dict:
        """Serializes the runbook to a dictionary. Useful for JSON serialization."""
        return {
            "raw_text": self.raw_text,
            "content": [content.model_dump() for content in self.content],
        }

    @classmethod
    def model_validate(cls, data: dict) -> "Runbook":
        """Create a runbook from a dictionary."""
        data = data.copy()
        content = cast(
            list[AnyRunbookContent],
            [
                RunbookContent.model_validate(content)
                for content in data.pop("content", [])
            ],
        )
        return cls(**data, content=content)
