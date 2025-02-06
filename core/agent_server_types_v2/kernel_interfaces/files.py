from abc import ABC, abstractmethod


class FilesInterface(ABC):
    """Handles interaction with files uploaded during agent chat sessions."""

    @abstractmethod
    async def todo(self) -> None:
        """TODO: figure out what methods we need here."""
        pass