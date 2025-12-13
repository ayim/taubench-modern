from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class EventsInterface(ABC, Generic[T]):
    """Generic event bus for asynchronous CA communication and downstream updates."""

    @abstractmethod
    async def dispatch(self, event: T) -> None:
        """Dispatch an event to the event bus.

        Arguments:
            event: The event to dispatch.
        """

    @abstractmethod
    def stream(self) -> AsyncGenerator[T, None]:
        """Stream events from the event bus.

        Returns:
            An asynchronous iterator of events.
        """

    @abstractmethod
    async def wait_for_event(self, predicate: Callable[[T], bool]) -> T:
        """Wait for an event matching the given predicate.

        Arguments:
            predicate: A function that returns True for the desired event.

        Returns:
            The first event for which predicate returns True.
        """
