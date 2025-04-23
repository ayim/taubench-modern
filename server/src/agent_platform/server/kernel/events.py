from asyncio import Event, Queue
from collections.abc import AsyncGenerator
from typing import cast

from agent_platform.core.kernel import EventsInterface
from agent_platform.core.streaming.delta import StreamingDelta
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerEventsInterface(EventsInterface, UsesKernelMixin):
    """Generic event bus for asynchronous communication and downstream updates.

    This implementation uses a sentinel value to signal the stream to stop.
    Calls to `dispatch` after `stop` will raise a RuntimeError.
    """

    def __init__(self) -> None:
        self._queue: Queue[StreamingDelta | object] = Queue()
        self._stop_event: Event = Event()
        self._sentinel = object()  # Unique object used to signal stop

    async def dispatch(self, event: StreamingDelta) -> None:
        """Dispatch an event to the event bus.

        Args:
            event: The event to dispatch.

        Raises:
            RuntimeError: If the event bus has been stopped.
        """
        if self._stop_event.is_set():
            raise RuntimeError("Event bus has been stopped")
        await self._queue.put(event)

    async def stream(self) -> AsyncGenerator[StreamingDelta, None]:
        """Stream events from the event bus until a stop is signaled.

        Yields:
            The next event from the event queue.
        """
        # Continue to yield events until the sentinel is encountered.
        while True:
            event = await self._queue.get()
            if event is self._sentinel:
                break
            yield cast(StreamingDelta, event)

    async def stop(self) -> None:
        """Stop the event stream.

        This method sets the stop event and enqueues a sentinel value to ensure that
        any awaiting stream is unblocked.
        """
        if not self._stop_event.is_set():
            self._stop_event.set()
            await self._queue.put(self._sentinel)
