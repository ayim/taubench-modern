from asyncio import Event, Queue
from collections.abc import AsyncIterator
from typing import Any

from agent_server_types_v2.kernel import EventsInterface
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerEventsInterface(EventsInterface, UsesKernelMixin):
    """Generic event bus for asynchronous communication and downstream updates.

    This implementation uses a sentinel value to signal the stream to stop.
    Calls to `dispatch` after `stop` will raise a RuntimeError.
    """

    def __init__(self) -> None:
        self._queue: Queue[Any] = Queue()
        self._stop_event: Event = Event()
        self._sentinel = object()  # Unique object used to signal stop

    async def dispatch(self, event: Any) -> None:
        """Dispatch an event to the event bus.

        Args:
            event: The event to dispatch.

        Raises:
            RuntimeError: If the event bus has been stopped.
        """
        if self._stop_event.is_set():
            raise RuntimeError("Event bus has been stopped")
        await self._queue.put(event)

    async def stream(self) -> AsyncIterator[Any]:
        """Stream events from the event bus until a stop is signaled.

        Yields:
            The next event from the event queue.
        """
        # Continue to yield events until the sentinel is encountered.
        while True:
            event = await self._queue.get()
            if event is self._sentinel:
                break
            yield event

    async def stop(self) -> None:
        """Stop the event stream.

        This method sets the stop event and enqueues a sentinel value to ensure that
        any awaiting stream is unblocked.
        """
        if not self._stop_event.is_set():
            self._stop_event.set()
            await self._queue.put(self._sentinel)