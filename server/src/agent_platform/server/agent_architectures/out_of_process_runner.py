from collections.abc import AsyncIterator

from agent_platform.core.kernel import Kernel
from agent_platform.core.streaming.delta import StreamingDelta
from agent_platform.server.agent_architectures.base_runner import BaseAgentRunner


class OutOfProcessAgentRunner(BaseAgentRunner):
    """Implementation of BaseAgentRunner that runs the CA in a separate process."""

    async def start(self) -> None:
        """Starts the out-of-process CA environment."""
        raise NotImplementedError("Out of process runner not implemented yet")

    async def invoke(self, kernel: Kernel) -> None:
        """Invokes the out-of-process CA with the given kernel."""
        raise NotImplementedError("Out of process runner not implemented yet")

    def get_event_stream(self) -> AsyncIterator[StreamingDelta]:
        """Returns an async iterator of events from the out-of-process CA."""
        raise NotImplementedError("Out of process runner not implemented yet")

    async def stop(self) -> None:
        """Cleanly stops the out-of-process CA runner."""
        raise NotImplementedError("Out of process runner not implemented yet")
