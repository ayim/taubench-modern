from dataclasses import dataclass, field
from typing import Literal, Self

from agent_server_types_v2.runbook.content import RunbookContent


@dataclass
class RunbookStepContent(RunbookContent):
    """This class represents a single structured step in a runbook."""

    name: str = field(
        metadata={
            "description": "The name of the step",
        },
    )
    """The name of the step"""

    content: str = field(
        metadata={
            "description": "The content of the step",
        },
    )
    """The content of the step"""

    metadata: dict = field(
        default_factory=dict,
        metadata={
            "description": "The metadata of the step",
        },
    )
    """The metadata of the step"""

    type: Literal["step"] = field(
        default="step",
        metadata={
            "description": "The type of content",
        },
    )
    """The type of content"""

    def copy(self) -> Self:
        """Returns a deep copy of the runbook step content."""
        return RunbookStepContent(
            name=self.name,
            content=self.content,
            metadata=self.metadata,
        )

    def to_json_dict(self) -> dict:
        """Serializes the runbook step content to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "content": self.content,
            "metadata": self.metadata,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunbookStepContent":
        """Create a runbook step content from a dictionary."""
        return cls(**data)
