from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class EventsInterface(ABC):
    """Generic event bus for asynchronous CA communication and downstream updates."""

    @abstractmethod
    async def dispatch(self, event: Any) -> None:
        """Dispatch an event to the event bus.

        Arguments:
            event: The event to dispatch.
        """
        pass

    @abstractmethod
    async def stream(self) -> AsyncIterator[Any]:
        """Stream events from the event bus.

        Returns:
            An asynchronous iterator of events.
        """
        pass
