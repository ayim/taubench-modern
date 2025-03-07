from agent_server_types_v2.kernel import ConvertersInterface
from agent_server_types_v2.prompts import (
    PromptAgentMessage,
    PromptMessage,
    PromptMessageContent,
    PromptTextContent,
    PromptUserMessage,
)
from agent_server_types_v2.thread import ThreadMessage, ThreadMessageContent
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerConvertersInterface(ConvertersInterface, UsesKernelMixin):
    """Interface for converting between thread, prompt, and response objects."""

    def __init__(self) -> None:
        self._kernel = None

    async def thread_contents_to_prompt_contents(
        self,
        contents: list[ThreadMessageContent],
    ) -> list[PromptMessageContent]:
        """Converts a thread content to a prompt content."""
        prompt_contents: list[PromptMessageContent] = []
        for content in contents:
            match content.kind:
                case "text":
                    prompt_contents.append(PromptTextContent(text=content.text))
                # TODO: tools and such
                case _:
                    raise ValueError(f"Unsupported thread content kind: {content.kind}")

        return prompt_contents

    async def thread_messages_to_prompt_messages(
        self,
        thread_messages: list[ThreadMessage],
    ) -> list[PromptMessage]:
        """Converts a list of thread messages to a list of prompt messages."""
        prompt_messages: list[PromptMessage] = []
        for message in thread_messages:
            match message.role:
                case "user":
                    prompt_messages.append(
                        PromptUserMessage(
                            content=await self.thread_contents_to_prompt_contents(
                                message.content,
                            ),
                        ),
                    )
                case "agent":
                    prompt_messages.append(
                        PromptAgentMessage(
                            content=await self.thread_contents_to_prompt_contents(
                                message.content,
                            ),
                        ),
                    )
                case _:
                    # Should never happen
                    raise ValueError(f"Unsupported thread message kind: {message.kind}")

        return prompt_messages
