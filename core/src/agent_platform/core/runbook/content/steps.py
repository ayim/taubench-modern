from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.runbook.content import RunbookContent
from agent_platform.core.runbook.content.step import RunbookStepContent


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

    kind: Literal["steps"] = field(
        default="steps",
        metadata={
            "description": "The kind of content",
        },
        init=False,
    )
    """The kind of content"""

    def copy(self) -> "RunbookStepsContent":
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
            "kind": self.kind,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookStepsContent":
        """Create a runbook steps content from a dictionary."""
        data = data.copy()
        steps = [
            RunbookStepContent.model_validate(step) for step in data.pop("steps", [])
        ]
        return cls(**data, steps=steps)

RunbookStepsContent.register_content_kind("steps", RunbookStepsContent)
