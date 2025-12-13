from collections.abc import Awaitable, Callable

from agent_platform.core.errors.base import ErrorCode, PlatformError
from agent_platform.core.kernel import ConvertersInterface, Kernel
from agent_platform.core.prompts.messages import AnyPromptMessage
from agent_platform.core.thread import ThreadMessage
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerConvertersInterface(ConvertersInterface, UsesKernelMixin):
    """Interface for converting between thread, prompt, and response objects."""

    def __init__(self) -> None:
        self._conversion_function: (
            Callable[
                [Kernel, list[ThreadMessage]],
                Awaitable[list[AnyPromptMessage]],
            ]
            | None
        ) = None

    def set_thread_message_conversion_function(
        self,
        conversion_function: Callable[[Kernel, list[ThreadMessage]], Awaitable[list[AnyPromptMessage]]],
    ) -> None:
        """Sets the function responsible for converting a list of thread messages
        to a list of prompt messages."""
        self._conversion_function = conversion_function

    async def thread_messages_to_prompt_messages(
        self,
        thread_messages: list[ThreadMessage],
    ) -> list[AnyPromptMessage]:
        """Converts a list of thread messages to a list of prompt messages."""
        if not self._conversion_function:
            raise PlatformError(
                error_code=ErrorCode.UNEXPECTED,
                message="No conversion function registered",
            )

        return await self._conversion_function(self.kernel, thread_messages)
