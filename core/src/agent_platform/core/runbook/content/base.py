from abc import ABC, abstractmethod
from typing import Self


class RunbookContent(ABC):
    """Base class for all runbook content types."""

    @property
    @abstractmethod
    def type(self) -> str:
        """The type of the runbook content."""
        pass

    @abstractmethod
    def model_dump(self) -> dict:
        """Serializes the runbook content to a dictionary.
        Useful for JSON serialization."""
        pass

    @abstractmethod
    def copy(self) -> Self:
        """Returns a deep copy of the runbook content."""
        pass
