from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.runbook.content import RunbookContent


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

    kind: Literal["step"] = field(
        default="step",
        metadata={
            "description": "The kind of content",
        },
        init=False,
    )
    """The kind of content"""

    def copy(self) -> "RunbookStepContent":
        """Returns a deep copy of the runbook step content."""
        return RunbookStepContent(
            name=self.name,
            content=self.content,
            metadata=self.metadata,
        )

    def model_dump(self) -> dict:
        """Serializes the runbook step content to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "content": self.content,
            "metadata": self.metadata,
            "kind": self.kind,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookStepContent":
        """Create a runbook step content from a dictionary."""
        return cls(**data)

RunbookStepContent.register_content_kind("step", RunbookStepContent)
