from agent_platform.core.kernel import Kernel
from agent_platform.core.prompts import (
    AgentPromptMessageContent,
    PromptAgentMessage,
    PromptUserMessage,
    UserPromptMessageContent,
)
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
from agent_platform.core.prompts.messages import AnyPromptMessage
from agent_platform.core.thread.base import AnyThreadMessageContent, ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.thought import ThreadThoughtContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.thread.messages import ThreadAgentMessage


async def _user_thread_contents_to_prompt_contents(
    contents: list[AnyThreadMessageContent],
) -> list[UserPromptMessageContent]:
    """Converts a thread content to a prompt content."""
    prompt_contents: list[UserPromptMessageContent] = []

    for content in contents:
        match content:
            case ThreadTextContent() as text_content:
                prompt_contents.append(
                    PromptTextContent(
                        text=text_content.text.strip(),
                    ),
                )
            case ThreadAttachmentContent() as attachment_content:
                prompt_contents.append(
                    PromptTextContent(
                        text=(f"Uploaded [{attachment_content.name}]({attachment_content.uri})."),
                    ),
                )
            # TODO: multi-modal content/docs
            case _:
                raise ValueError(f"Unsupported thread content kind: {content.kind}")

    return prompt_contents


async def _agent_thread_contents_to_prompt_contents(
    contents: list[AnyThreadMessageContent],
) -> tuple[list[AgentPromptMessageContent], list[UserPromptMessageContent]]:
    """Converts a thread content to a prompt content."""
    prompt_agent_contents: list[AgentPromptMessageContent] = []
    prompt_user_contents: list[UserPromptMessageContent] = []

    thought_text = ""
    response_text = ""
    for content in contents:
        match content:
            case ThreadThoughtContent() as thought_content:
                thought_text += f"{thought_content.thought.strip()}\n"
            case ThreadTextContent() as text_content:
                response_text += f"{text_content.text.strip()}\n"
            case ThreadToolUsageContent() as tool_usage_content:
                prompt_agent_contents.append(
                    PromptToolUseContent(
                        tool_call_id=tool_usage_content.tool_call_id,
                        tool_name=tool_usage_content.name,
                        tool_input_raw=tool_usage_content.arguments_raw,
                    ),
                )
                prompt_user_contents.append(
                    PromptToolResultContent(
                        tool_call_id=tool_usage_content.tool_call_id,
                        tool_name=tool_usage_content.name,
                        content=[
                            PromptTextContent(
                                text=tool_usage_content.result or "",
                            ),
                        ],
                        is_error=tool_usage_content.status == "failed",
                    ),
                )
            # TODO: multi-modal content/docs
            case _:
                raise ValueError(f"Unsupported thread content kind: {content.kind}")

    collapsed_text = "<response>\n"
    collapsed_text += response_text
    collapsed_text += "\n</response>"

    prompt_agent_contents = [
        # Prepend the collapsed text
        PromptTextContent(
            text=collapsed_text.strip(),
        ),
        *prompt_agent_contents,
    ]

    return prompt_agent_contents, prompt_user_contents


async def thread_messages_to_prompt_messages(
    kernel: Kernel,
    thread_messages: list[ThreadMessage],
) -> list[AnyPromptMessage]:
    """Convert a list of thread messages to a list of prompt messages."""
    prompt_messages: list[AnyPromptMessage] = []
    active_message = ThreadAgentMessage(
        role="agent",
        content=kernel.thread_state.active_message_content,
    )
    for message in [*thread_messages, active_message]:
        match message.role:
            case "user":
                prompt_messages.append(
                    PromptUserMessage(
                        content=await _user_thread_contents_to_prompt_contents(
                            message.content,
                        ),
                    ),
                )
            case "agent":
                # There's a split here for things like tool calling: agent decides
                # to call a tool, and then the user provides the result.
                (
                    agent_contents,
                    user_contents,
                ) = await _agent_thread_contents_to_prompt_contents(message.content)

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
