from dataclasses import dataclass, field
from typing import Literal, Self

from agent_server_types_v2.runbook.content import RunbookContent
from agent_server_types_v2.runbook.content.step import RunbookStepContent


@dataclass
class RunbookStepsContent(RunbookContent):
    """This class represents a structured sequence of
    steps to be executed, as defined in a runbook."""

    steps: list[RunbookStepContent] = field(
        metadata={
            "description": "The steps to be executed",
        },
    )
    """The steps to be executed"""

    metadata: dict = field(
        default_factory=dict,
        metadata={
            "description": "Any extra metadata for the steps collection",
        },
    )
    """Any extra metadata for the steps collection"""

    type: Literal["steps"] = field(
        default="steps",
        metadata={
            "description": "The type of content",
        },
    )
    """The type of content"""

    def copy(self) -> Self:
        """Returns a deep copy of the runbook steps content."""
        return RunbookStepsContent(
            steps=[step.copy() for step in self.steps],
            metadata=self.metadata,
        )

    def to_json_dict(self) -> dict:
        """Serializes the runbook steps content to a dictionary.
        Useful for JSON serialization."""
        return {
            "steps": [step.to_json_dict() for step in self.steps],
            "metadata": self.metadata,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunbookStepsContent":
        """Create a runbook steps content from a dictionary."""
        data = data.copy()
        steps = [
            RunbookStepContent.from_dict(step) for step in data.pop("steps", [])
        ]
        return cls(**data, steps=steps)
