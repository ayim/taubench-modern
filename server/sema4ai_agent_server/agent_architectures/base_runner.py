from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from agent_server_types_v2.kernel import Kernel


class BaseAgentRunner(ABC):
    """Represents a running Agent Architecture environment.

    This abstract base class defines the interface for managing agent architecture
    environments, whether running in-process or out-of-process. It provides a uniform
    interface for the server to interact with any agent architecture implementation.

    The server can start, invoke, and stop the agent architecture by passing a kernel
    instance (either local or remote) without needing to know the specific
    implementation details of the agent architecture.
    """

    @abstractmethod
    async def start(self) -> None:
        """Starts or initializes the agent architecture environment if it isn't
        already running.

        This method should handle any necessary setup, resource allocation,
        or process initialization required by the specific agent architecture
        implementation.
        """
        pass

    @abstractmethod
    async def invoke(self, kernel: Kernel) -> None:
        """Invokes the agent architecture with the given kernel.

        Arguments:
            kernel: A Kernel instance that provides the interface for the agent
                    architecture to interact with its environment.
        """
        pass

    @abstractmethod
    def get_event_stream(self) -> AsyncIterator[Any]:
        """Returns an async iterator of events from the agent architecture.

        Returns:
            An async iterator yielding dictionaries containing agent architecture
            events. The specific structure of these event dictionaries should be
            documented by the implementing class.
        """
        pass

    @abstractmethod
    async def dispatch_event(self, event: Any) -> None:
        """Dispatches an event to the Agent Architecture.

        Arguments:
            event: The event to dispatch to the Agent Architecture.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Cleanly stops the agent architecture runner.

        This method should handle proper cleanup, including:
        - Freeing allocated resources
        - Terminating any subprocesses
        - Closing open connections
        - Saving any necessary state
        """
        pass
