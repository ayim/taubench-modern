from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuestionGroup:
    """Agent question group definition."""

    title: str = field(metadata={"description": "The title of the question group."})
    """The title of the question group."""

    questions: list[str] = field(
        metadata={"description": "The questions in the question group."},
        default_factory=list,
    )
    """The questions in the question group."""

    def copy(self) -> "QuestionGroup":
        """Returns a deep copy of the question group."""
        return QuestionGroup(
            title=self.title,
            questions=self.questions,
        )

    def model_dump(self) -> dict:
        """Serializes the question group to a dictionary.
        Useful for JSON serialization."""
        return {
            "title": self.title,
            "questions": self.questions,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "QuestionGroup":
        """Create a question group from a dictionary."""
        return cls(**data)
