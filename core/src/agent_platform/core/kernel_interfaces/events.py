from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from agent_platform.core.streaming.delta import StreamingDelta


class EventsInterface(ABC):
    """Generic event bus for asynchronous CA communication and downstream updates."""

    @abstractmethod
    async def dispatch(self, event: StreamingDelta) -> None:
        """Dispatch an event to the event bus.

        Arguments:
            event: The event to dispatch.
        """
        pass

    @abstractmethod
    def stream(self) -> AsyncGenerator[StreamingDelta, None]:
        """Stream events from the event bus.

        Returns:
            An asynchronous iterator of events.
        """
        pass
