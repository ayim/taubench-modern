from asyncio import Event, Future, Queue
from collections.abc import AsyncGenerator, Callable
from typing import Any, Generic, TypeVar, cast

from agent_platform.core.kernel import EventsInterface
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

T = TypeVar("T")


class AgentServerEventsInterface(EventsInterface[T], UsesKernelMixin, Generic[T]):
    """Generic event bus for asynchronous communication and downstream updates.

    This implementation uses a sentinel value to signal the stream to stop.
    Calls to `dispatch` after `stop` will raise a RuntimeError.

    Supports multiple concurrent waiters for different events.
    """

    def __init__(self) -> None:
        from dataclasses import dataclass

        @dataclass
        class _EventWaiter:
            """Internal class to track waiters for specific events."""

            predicate: Callable[[Any], bool]
            future: Future[Any]

        self._EventWaiter = _EventWaiter
        self._queue: Queue[T | object] = Queue()
        self._stop_event: Event = Event()
        self._sentinel = object()  # Unique object used to signal stop
        self._waiters: list[_EventWaiter] = []  # Active waiters

    async def dispatch(self, event: T) -> None:
        """Dispatch an event to the event bus.

        Args:
            event: The event to dispatch.

        Raises:
            RuntimeError: If the event bus has been stopped.
        """
        if self._stop_event.is_set():
            raise RuntimeError("Event bus has been stopped")

        # First, check if any active waiters are waiting for this event
        matched_waiters = []
        remaining_waiters = []

        for waiter in self._waiters:
            if waiter.predicate(event):
                matched_waiters.append(waiter)
            else:
                remaining_waiters.append(waiter)

        # Update the waiters list to remove matched ones
        self._waiters = remaining_waiters

        # Resolve futures for matched waiters
        for waiter in matched_waiters:
            if not waiter.future.done():
                waiter.future.set_result(event)

        # If no waiters matched, put the event in the general queue for stream() consumers
        if not matched_waiters:
            await self._queue.put(event)

    async def stream(self) -> AsyncGenerator[T, None]:
        """Stream events from the event bus until a stop is signaled.

        Yields:
            The next event from the event queue.
        """
        # Continue to yield events until the sentinel is encountered.
        while True:
            event = await self._queue.get()
            if event is self._sentinel:
                break
            yield cast(T, event)

    async def stop(self) -> None:
        """Stop the event stream.

        This method sets the stop event and enqueues a sentinel value to ensure that
        any awaiting stream is unblocked.
        """
        if not self._stop_event.is_set():
            self._stop_event.set()
            await self._queue.put(self._sentinel)

            # Cancel any remaining waiters
            for waiter in self._waiters:
                if not waiter.future.done():
                    waiter.future.cancel()
            self._waiters.clear()

    async def wait_for_event(self, predicate: Callable[[T], bool]) -> T:
        """Wait for an event matching the given predicate.

        Arguments:
            predicate: A function that returns True for the desired event.

        Returns:
            The first event for which predicate returns True.

        Raises:
            RuntimeError: If the event stream ends before finding a matching event.
        """
        if self._stop_event.is_set():
            raise RuntimeError("Event bus has been stopped")

        # Create a future to wait for the event
        future: Future[T] = Future()
        waiter = self._EventWaiter(predicate=predicate, future=future)

        # Add to the list of active waiters
        self._waiters.append(waiter)

        try:
            # Wait for the future to be resolved
            return await future
        except Exception:
            # If cancelled or failed, remove from waiters list
            if waiter in self._waiters:
                self._waiters.remove(waiter)
            raise
