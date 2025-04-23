from agent_platform.core.agent import Agent
from agent_platform.core.kernel import ThreadStateInterface
from agent_platform.core.streaming import StreamingDelta
from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerThreadStateInterface(ThreadStateInterface, UsesKernelMixin):
    """Manages the in-memory representation of the current thread."""

    def __init__(self, thread: Thread, agent: Agent):
        self._thread = thread
        self._agent = agent
        super().__init__(thread.thread_id, agent.agent_id)

    async def _send_delta_event(self, delta_object: StreamingDelta) -> None:
        """Sends a delta event to the UI.

        Arguments:
            delta_object: The computed delta between the previous and current
                message state. Contains the changes that need to be sent to the UI.

        Raises:
            StreamingError: If the delta cannot be sent to the UI.
        """
        await self.kernel.outgoing_events.dispatch(delta_object)

    async def _commit_message_to_storage(self, message: ThreadMessage) -> None:
        """Commits a message to the thread state storage.

        Arguments:
            message: The message to commit to storage.

        Raises:
            Exception: If the message cannot be committed to storage.
        """
        await self.kernel.storage.put_message(message)
        # Make sure we also update the thread in memory
        self._thread.messages.append(message)
