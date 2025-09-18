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


async def _get_file_name_and_path(
    kernel: Kernel,
    attachment_content: ThreadAttachmentContent,
) -> tuple[str | None, str | None]:
    """Gets the name and ref of a file from an attachment content."""
    if not attachment_content.uri:
        return None, None
    file_id = attachment_content.uri.replace("agent-server-file://", "")
    file_details = await kernel.files.get_file_by_id(file_id)
    if not file_details:
        return None, None
    return file_details.file_ref, file_details.file_path


async def _user_thread_contents_to_prompt_contents(
    kernel: Kernel,
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
                file_name, file_path = await _get_file_name_and_path(kernel, attachment_content)
                if file_name and file_path:
                    prompt_contents.append(
                        PromptTextContent(
                            text=(f"Uploaded [{file_name}]({file_path})."),
                        ),
                    )
            # TODO: multi-modal content/docs
            case _:
                raise ValueError(f"Unsupported thread content kind: {content.kind}")

    return prompt_contents


async def _agent_thread_contents_to_prompt_contents(
    contents: list[AnyThreadMessageContent],
    step: str,
) -> tuple[list[AgentPromptMessageContent], list[UserPromptMessageContent]]:
    """Converts a thread content to a prompt content."""
    prompt_agent_contents: list[AgentPromptMessageContent] = []
    prompt_user_contents: list[UserPromptMessageContent] = []

    # NOTE: here, much more than elsewhere, we must be very careful of "context
    # poisoning" --- it's all too easy to slightly format something wrong and
    # have a prompt that's confusing to the LLM.

    thought_text = ""
    response_text = ""
    for content in contents:
        match content:
            case ThreadThoughtContent() as thought_content:
                thought_text += f"{thought_content.thought.strip()}\n"
            case ThreadTextContent() as text_content:
                response_text += f"{text_content.text.strip()}\n"
            case ThreadToolUsageContent() as tool_usage_content:
                tool_output = tool_usage_content.result or ""
                if tool_usage_content.error:
                    tool_output += f"\nError: {tool_usage_content.error}"
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
                                text=tool_output,
                            ),
                        ],
                        is_error=tool_usage_content.status == "failed",
                    ),
                )
            # TODO: multi-modal content/docs
            case _:
                raise ValueError(f"Unsupported thread content kind: {content.kind}")

    # Now we need to take a run of prompt text <thinking>...</thinking>
    # and a run of prompt text <response>...</response> and combine them
    # into a single <formatting>...</formatting> tag.
    collapsed_text = "<formatting>\n<thinking>\n"
    collapsed_text += thought_text
    collapsed_text += "\n</thinking>\n<response>\n"
    collapsed_text += response_text
    collapsed_text += f"\n</response>\n<step>{step}</step>\n</formatting>"

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
    for idx, message in enumerate(thread_messages):
        match message.role:
            case "user":
                prompt_messages.append(
                    PromptUserMessage(
                        content=await _user_thread_contents_to_prompt_contents(
                            kernel,
                            message.content,
                        ),
                    ),
                )
            case "agent":
                # If the next message was a user message, this agent
                # message should have been marked <step>done</step>
                step = "processing"
                if idx + 1 < len(thread_messages) and thread_messages[idx + 1].role == "user":
                    step = "done"

                # There's a split here for things like tool calling: agent decides
                # to call a tool, and then the user provides the result.
                (
                    agent_contents,
                    user_contents,
                ) = await _agent_thread_contents_to_prompt_contents(
                    message.content,
                    step,
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
