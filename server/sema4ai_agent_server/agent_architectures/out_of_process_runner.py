from collections.abc import AsyncIterator

from agent_server_types_v2.kernel import Kernel
from sema4ai_agent_server.agent_architectures.base_runner import BaseAgentRunner


class OutOfProcessAgentRunner(BaseAgentRunner):
    """Implementation of BaseAgentRunner that runs the CA in a separate process."""

    async def start(self) -> None:
        """Starts the out-of-process CA environment."""
        raise NotImplementedError("Out of process runner not implemented yet")

    async def invoke(self, kernel: Kernel) -> None:
        """Invokes the out-of-process CA with the given kernel."""
        raise NotImplementedError("Out of process runner not implemented yet")

    def get_event_stream(self) -> AsyncIterator[dict]:
        """Returns an async iterator of events from the out-of-process CA."""
        raise NotImplementedError("Out of process runner not implemented yet")

    async def stop(self) -> None:
        """Cleanly stops the out-of-process CA runner."""
        raise NotImplementedError("Out of process runner not implemented yet")
