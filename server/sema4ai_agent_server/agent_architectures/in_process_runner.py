from collections.abc import AsyncIterator
from typing import Any

from agent_server_types_v2.kernel import Kernel
from sema4ai_agent_server.agent_architectures.base_runner import BaseAgentRunner


class InProcessAgentRunner(BaseAgentRunner):
    """Runs the CA logic in the same Python process. For trusted CAs only."""

    def __init__(self, package_name: str, version: str, thread_id: str):
        self.package_name = package_name
        self.version = version
        self.thread_id = thread_id
        self.entry_func = None

        self._started = False
        self._kernel = None

    async def start(self) -> None:
        from importlib.metadata import entry_points

        # If the CA is already started, do nothing
        if self._started:
            return

        # Possibly load the CA entrypoint:
        self._started = True
        entry_points = entry_points(group="agent_architectures")

        self.entry_func = None
        for ep in entry_points:
            if ep.name == self.package_name:
                self.entry_func = ep.load()
                break

        if not self.entry_func:
            raise RuntimeError(f"No entrypoint found for {self.package_name}")

        # You might also do some “init” if the CA has a stateful setUp
        # Or spawn a background task for reading events, etc. Up to you.

    async def invoke(self, kernel: Kernel) -> None:
        try:
            self._kernel = kernel
            await self.entry_func(kernel)
        except Exception as e:
            await self._kernel.outgoing_events.dispatch(f"Error in CA: {e}")

    def get_event_stream(self) -> AsyncIterator[Any]:
        return self._kernel.outgoing_events.stream()

    async def stop(self) -> None:
        await self._kernel.outgoing_events.stop()

    async def dispatch_event(self, event: Any):
        await self._kernel.incoming_events.dispatch(event)