from agent_platform.core.agent_architectures.thread_conversion_utils import ThreadConversionState
from agent_platform.core.kernel import Kernel
from agent_platform.core.prompts import (
    AgentPromptMessageContent,
    PromptAgentMessage,
    PromptUserMessage,
    UserPromptMessageContent,
)
from agent_platform.core.prompts.content.reasoning import PromptReasoningContent
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
from agent_platform.core.prompts.messages import AnyPromptMessage
from agent_platform.core.thread.base import AnyThreadMessageContent, ThreadMessage
from agent_platform.core.thread.content.quick_actions import ThreadQuickActionsContent
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.thought import ThreadThoughtContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.thread.content.vega_chart import ThreadVegaChartContent
from agent_platform.core.thread.messages import ThreadAgentMessage


async def _agent_thread_contents_to_prompt_contents(
    contents: list[AnyThreadMessageContent],
) -> tuple[list[AgentPromptMessageContent], list[UserPromptMessageContent]]:
    """Converts a thread content to a prompt content."""
    prompt_agent_contents: list[AgentPromptMessageContent] = []
    prompt_user_contents: list[UserPromptMessageContent] = []

    for content in contents:
        match content:
            case ThreadThoughtContent() as thought_content:
                if thought_content.extras.get("encrypted_content"):
                    embedded_response = thought_content.extras.copy()
                    embedded_response.pop("kind", None)
                    embedded_response.pop("metadata", None)
                    prompt_agent_contents.append(
                        PromptReasoningContent(**embedded_response),
                    )
            case ThreadTextContent() as text_content:
                if text_content.text:
                    prompt_agent_contents.append(
                        PromptTextContent(text=text_content.text),
                    )
            case ThreadVegaChartContent():
                # We are generating charts out-of-band, so it doesn't make sense to pollute
                # context with the chart spec.
                continue
            case ThreadQuickActionsContent():
                # Buttons are rendered inline; they should not affect prompt context.
                continue
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

    return prompt_agent_contents, prompt_user_contents


def _group_contents_by_prompt_index(
    contents: list[AnyThreadMessageContent],
    content_idx_to_prompt_idx: dict,
) -> list[list[AnyThreadMessageContent]]:
    """Groups contents into ordered buckets by prompt index.

    Requires a mapping from content index -> prompt index. Keys must be strings.
    """

    def _get_prompt_idx_for(content_index: int) -> int:
        value = content_idx_to_prompt_idx.get(str(content_index), 0)
        if not isinstance(value, int):
            raise ValueError(
                f"Prompt index for content index {content_index} must be an int, got: {type(value).__name__}"
            )
        return value

    buckets_by_prompt_idx: dict[int, list[AnyThreadMessageContent]] = {}
    encounter_order: list[int] = []

    for idx, content in enumerate(contents):
        prompt_idx = _get_prompt_idx_for(idx)
        if prompt_idx not in buckets_by_prompt_idx:
            buckets_by_prompt_idx[prompt_idx] = []
            encounter_order.append(prompt_idx)
        buckets_by_prompt_idx[prompt_idx].append(content)

    return [buckets_by_prompt_idx[p_idx] for p_idx in encounter_order]


async def thread_messages_to_prompt_messages(
    kernel: Kernel,
    thread_messages: list[ThreadMessage],
    state: ThreadConversionState | None = None,
) -> list[AnyPromptMessage]:
    """Convert a list of thread messages to a list of prompt messages."""
    from agent_platform.core.agent_architectures.thread_conversion_utils import (
        user_thread_contents_to_prompt_contents,
    )

    prompt_messages: list[AnyPromptMessage] = []
    active_message = ThreadAgentMessage(
        role="agent",
        content=kernel.thread_state.active_message_content,
    )
    for message in [*thread_messages, active_message]:
        match message.role:
            case "user":
                user_contents = await user_thread_contents_to_prompt_contents(
                    kernel,
                    message.content,
                    state=state,
                )
                # Avoid emitting empty Bedrock messages (which cause ValidationException)
                if len(user_contents) > 0:
                    prompt_messages.append(
                        PromptUserMessage(content=user_contents),
                    )
            case "agent":
                content_idx_to_prompt_idx = message.agent_metadata.get(
                    "content_idx_to_prompt_idx",
                    {},
                )
                grouped_contents = _group_contents_by_prompt_index(message.content, content_idx_to_prompt_idx)

                for grouped in grouped_contents:
                    agent_contents, user_contents = await _agent_thread_contents_to_prompt_contents(grouped)
                    if len(agent_contents) > 0:
                        prompt_messages.append(PromptAgentMessage(content=agent_contents))
                    if len(user_contents) > 0:
                        prompt_messages.append(PromptUserMessage(content=user_contents))
            case _:
                # Should never happen
                raise ValueError(f"Unsupported thread message kind: {message.kind}")

    return prompt_messages
