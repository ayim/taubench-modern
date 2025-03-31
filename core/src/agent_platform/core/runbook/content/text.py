from dataclasses import dataclass, field

from agent_platform.core.runbook.content import RunbookContent


@dataclass
class RunbookTextContent(RunbookContent):
    """This class represents a simple text content component in a runbook."""

    content: str = field(
        metadata={
            "description": "The content of the text",
        },
    )
    """The content of the text"""

    kind: str = field(
        default="text",
        metadata={
            "description": "The kind of content",
        },
        init=False,
    )
    """The kind of content"""

    def __post_init__(self) -> None:
        """Validates the content type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "text".
        """
        assert self.kind == "text"

    def copy(self) -> "RunbookTextContent":
        """Returns a deep copy of the runbook text content."""
        return RunbookTextContent(
            content=self.content,
        )

    def model_dump(self) -> dict:
        """Serializes the runbook text content to a dictionary.
        Useful for JSON serialization."""
        return {
            "content": self.content,
            "kind": self.kind,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "RunbookTextContent":
        """Create a runbook text content from a dictionary."""
        return cls(**data)

RunbookTextContent.register_content_kind("text", RunbookTextContent)
