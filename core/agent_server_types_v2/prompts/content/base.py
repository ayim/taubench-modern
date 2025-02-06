from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptMessageContent(ABC):
    """Base class for all prompt message content types."""

    @property
    @abstractmethod
    def type(self) -> str:
        """The type of the prompt message content."""
        pass