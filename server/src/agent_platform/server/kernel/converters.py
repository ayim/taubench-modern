from agent_platform.core.kernel import ConvertersInterface
from agent_platform.core.prompts import (
    AgentPromptMessageContent,
    PromptAgentMessage,
    PromptMessage,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
    UserPromptMessageContent,
)
from agent_platform.core.thread import (
    AnyThreadMessageContent,
    ThreadMessage,
    ThreadTextContent,
    ThreadThoughtContent,
    ThreadToolUsageContent,
)
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerConvertersInterface(ConvertersInterface, UsesKernelMixin):
    """Interface for converting between thread, prompt, and response objects."""

    def __init__(self) -> None:
        self._kernel = None

    async def user_thread_contents_to_prompt_contents(
        self,
        contents: list[AnyThreadMessageContent],
    ) -> list[UserPromptMessageContent]:
        """Converts a thread content to a prompt content."""
        prompt_contents: list[UserPromptMessageContent] = []

        for content in contents:
            match content:
                case ThreadTextContent() as text_content:
                    prompt_contents.append(PromptTextContent(
                        text=text_content.text.strip(),
                    ))
                # TODO: multi-modal content/docs
                case _:
                    raise ValueError(f"Unsupported thread content kind: {content.kind}")

        return prompt_contents

    async def agent_thread_contents_to_prompt_contents(
        self,
        contents: list[AnyThreadMessageContent],
    ) -> tuple[list[AgentPromptMessageContent], list[UserPromptMessageContent]]:
        """Converts a thread content to a prompt content."""
        prompt_agent_contents: list[AgentPromptMessageContent] = []
        prompt_user_contents: list[UserPromptMessageContent] = []

        for content in contents:
            match content:
                case ThreadThoughtContent() as thought_content:
                    prompt_agent_contents.append(PromptTextContent(
                        text=f"<thinking>\n{thought_content.thought.strip()}\n</thinking>\n",
                    ))
                case ThreadTextContent() as text_content:
                    prompt_agent_contents.append(PromptTextContent(
                        text=f"<response>\n{text_content.text.strip()}\n</response>\n",
                    ))
                case ThreadToolUsageContent() as tool_usage_content:
                    prompt_agent_contents.append(PromptToolUseContent(
                        tool_call_id=tool_usage_content.tool_call_id,
                        tool_name=tool_usage_content.name,
                        tool_input_raw=tool_usage_content.arguments_raw,
                    ))
                    prompt_user_contents.append(PromptToolResultContent(
                        tool_call_id=tool_usage_content.tool_call_id,
                        tool_name=tool_usage_content.name,
                        content=[
                            PromptTextContent(
                                text=tool_usage_content.result or "",
                            ),
                        ],
                        is_error=tool_usage_content.status == "failed",
                    ))
                # TODO: multi-modal content/docs
                case _:
                    raise ValueError(f"Unsupported thread content kind: {content.kind}")

        return prompt_agent_contents, prompt_user_contents

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
                            content=await self.user_thread_contents_to_prompt_contents(
                                message.content,
                            ),
                        ),
                    )
                case "agent":
                    # There's a split here for things like tool calling: agent decides
                    # to call a tool, and then the user provides the result.
                    agent_contents, user_contents = (
                        await self.agent_thread_contents_to_prompt_contents(
                            message.content,
                        )
                    )

                    prompt_messages.append(
                        PromptAgentMessage(content=agent_contents),
                    )
                    if len(user_contents) > 0:
                        prompt_messages.append(
                            PromptUserMessage(content=user_contents),
                        )
                case _:
                    # Should never happen
                    raise ValueError(f"Unsupported thread message kind: {message.kind}")

        return prompt_messages
