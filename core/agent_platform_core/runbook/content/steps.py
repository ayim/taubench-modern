from dataclasses import dataclass, field
from typing import Literal, Self

from agent_platform_core.runbook.content import RunbookContent
from agent_platform_core.runbook.content.step import RunbookStepContent


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

    def model_dump(self) -> dict:
        """Serializes the runbook steps content to a dictionary.
        Useful for JSON serialization."""
        return {
            "steps": [step.model_dump() for step in self.steps],
            "metadata": self.metadata,
            "type": self.type,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookStepsContent":
        """Create a runbook steps content from a dictionary."""
        data = data.copy()
        steps = [
            RunbookStepContent.model_validate(step) for step in data.pop("steps", [])
        ]
        return cls(**data, steps=steps)
