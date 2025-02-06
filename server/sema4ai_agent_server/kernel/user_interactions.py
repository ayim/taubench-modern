from asyncio import wait_for

from agent_server_types_v2.kernel_interfaces import UserInteractionsInterface
from agent_server_types_v2.thread import ThreadTextContent, ThreadUserMessage
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerUserInteractionsInterface(UserInteractionsInterface, UsesKernelMixin):
    """Access to the user in the kernel interface."""

    async def prompt_user(self, timeout_seconds: float = 120.0) -> ThreadUserMessage:
        """Prompts the user for input and blocks until the user responds.

        Returns:
            The user's response as a ThreadUserMessage.

        Raises:
            TimeoutError: If the user fails to respond within timeout_seconds.
        """

        # Step 1: Notify downstream (e.g. a UI or user prompt handler) that we are waiting for user input.
        prompt_event = {
            "type": "user_message_request", 
            "message": "Awaiting user input...",
            "timeout": timeout_seconds,
        }
        await self.kernel.outgoing_events.dispatch(prompt_event)

        # Step 2: Wait for the user's response by polling the incoming events stream.
        async def wait_for_response() -> ThreadUserMessage:
            async for event in self.kernel.incoming_events.stream():
                # Check if the event is indeed a user response.
                if isinstance(event, dict) and event["type"] == "user_message_reply":
                    return ThreadUserMessage(content=[ThreadTextContent(text=event["input"])])

        try:
            # Wrap the waiting coroutine with a timeout.
            user_response = await wait_for(wait_for_response(), timeout=timeout_seconds)
            return user_response
        except TimeoutError as e:
            raise TimeoutError(f"User did not respond within {timeout_seconds} seconds.") from e
