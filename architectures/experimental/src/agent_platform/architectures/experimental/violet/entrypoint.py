import logging
from collections.abc import Iterable

from agent_platform.architectures.experimental.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.kernel_interfaces import PlatformInterface
from agent_platform.core.kernel_interfaces.tools import ThreadMessageWithThreadState
from agent_platform.core.prompts.content import (
    PromptReasoningContent,
    PromptTextContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.messages import AnyPromptMessage, PromptAgentMessage
from agent_platform.core.responses import ResponseToolUseContent
from agent_platform.core.thread import ThreadMessage
from agent_platform.core.tools import ToolExecutionResult
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 25


async def entrypoint_violet(kernel: Kernel, state: VioletState) -> VioletState:
    """
    Top-level entrypoint. Initializes state and runs the processing pipeline.
    """
    try:
        from agent_platform.core.agent_architectures.special_commands import (
            handle_special_command,
            parse_special_command,
        )

        logger.info("Violet architecture starting")
        # Check for exact-match special commands on the latest user message
        try:
            latest_user_text = kernel.thread.latest_user_message_as_text
        except Exception:
            latest_user_text = ""
        cmd = parse_special_command(latest_user_text)
        if cmd is not None:
            logger.info(f"Special command detected: {cmd}; bypassing normal loop.")
            handled = await handle_special_command(
                cmd,
                kernel,
                state=state,  # type: ignore[arg-type] (VioletState is a subclass of ArchState)
                internal_tools_provider=lambda: (),
            )
            if handled:
                state.step = "done"
                return state
            # If not handled for some reason, continue to normal flow
        return await _process_conversation_step(kernel, state)
    except Exception:
        logger.error("Violet architecture failed", exc_info=True)
        raise
    finally:
        logger.info("Violet architecture completed")


@aa.step
async def _process_conversation_step(kernel: Kernel, state: VioletState) -> VioletState:
    """
    The main multi-iteration tool loop + final-reply flow.
    """
    from functools import partial

    from agent_platform.architectures.experimental.violet.docintel.manager import DocIntelManager
    from agent_platform.architectures.experimental.violet.prompts import build_prompt
    from agent_platform.architectures.experimental.violet.streaming import (
        PIPE_MAIN_PROMPT,
        stream_with_retry,
    )
    from agent_platform.architectures.experimental.violet.tools_registry import ToolsRegistry

    # 1. Setup
    kernel.converters.set_thread_message_conversion_function(
        partial(violet_thread_messages_to_prompt_messages, state=state)
    )

    # 2. Create Message
    message = await kernel.thread_state.new_agent_message()
    state.current_iteration = 0

    # 3. Initialize Tools Registry
    registry = ToolsRegistry(kernel, state, message)

    # 4. Initialize Doc Intel Manager
    doc_mgr = DocIntelManager(kernel, state)

    # 5. Run Doc Intel Lifecycle (Hydrate -> Scan -> Sample -> Check Lock)
    #    This returns True if we need to stop for User Input (Markup)
    should_halt = await doc_mgr.ensure_active_state(message)

    if should_halt:
        # Commit the message requesting markup and exit
        await message.commit()
        return state

    # 6. Process Missing Schemas
    #    This runs inference if cards are Done but have no schema.
    await doc_mgr.process_missing_schemas(message)

    # 7. Gather Tools (now that schemas might be ready)
    tools_bundle = await registry.gather(message)

    # 8. Main LLM Loop
    while state.step != "done" and state.current_iteration < MAX_ITERATIONS:
        state.current_iteration += 1
        _update_elapsed_time(state)

        platform, model = await _resolve_platform_and_model(kernel, state)

        logger.info(f"Iteration {state.current_iteration}/{MAX_ITERATIONS} (model={model})")

        conversation_prompt = await build_prompt(
            kernel=kernel,
            state=state,
            prompt_path="prompts/main",
            tools=tools_bundle.as_tuple(),
        )

        await stream_with_retry(
            platform=platform,
            model=model,
            prompt=conversation_prompt,
            message=message,
            state=state,
            spec=PIPE_MAIN_PROMPT,
        )

        pending = list(state.pending_tool_calls)
        if not pending:
            state.step = "done"
            break

        await _mark_tools_running(message, state.pending_tool_calls)
        await _execute_pending_tools(kernel, state, message)
        state.pending_tool_calls.clear()

    await message.commit()
    return state


async def _resolve_platform_and_model(
    kernel: Kernel, state: VioletState
) -> tuple[PlatformInterface, str]:
    """Resolves the platform and model, and updates the state with the details."""
    platform, model_str = await kernel.get_platform_and_model(model_type="llm")
    logger.info("Using model: %s", model_str)

    # Expected format: "platform/provider/model_name"
    parts = model_str.split("/")
    if len(parts) == 3:  # noqa: PLR2004
        state.selected_platform, state.selected_model_provider, state.selected_model = parts
    else:
        state.selected_platform = platform.name
        state.selected_model_provider = "unknown"
        state.selected_model = model_str

    return platform, model_str


def _update_elapsed_time(state: VioletState) -> None:
    from datetime import UTC, datetime

    elapsed_seconds = (
        datetime.now(UTC) - datetime.fromisoformat(state.processing_start_time)
    ).total_seconds()
    state.processing_elapsed_time = f"{elapsed_seconds:.2f} seconds"


async def _mark_tools_running(
    message: ThreadMessageWithThreadState,
    pending_tool_calls: Iterable[tuple[ToolDefinition, ResponseToolUseContent]],
) -> None:
    pending_list = list(pending_tool_calls)
    logger.info("Pending tool calls: %s", len(pending_list))
    for _, tool_call in pending_list:
        message.update_tool_running(tool_call.tool_call_id)
    await message.stream_delta()


async def _execute_pending_tools(
    kernel: Kernel,
    state: VioletState,
    message: ThreadMessageWithThreadState,
) -> list[ToolExecutionResult]:
    recent: list[ToolExecutionResult] = []
    async for result in kernel.tools.execute_pending_tool_calls(state.pending_tool_calls, message):
        recent.append(result)

    return recent


async def violet_thread_messages_to_prompt_messages(
    kernel: Kernel,
    thread_messages: list[ThreadMessage],
    state: VioletState | None = None,
) -> list[AnyPromptMessage]:
    def _should_ignore_reasoning(
        content: PromptReasoningContent | PromptTextContent | PromptToolUseContent,
    ) -> bool:
        ignored_ids = state.ignored_reasoning_ids if state else []
        return content.kind == "reasoning" and content.response_id in ignored_ids

    # We want to do the default, but strip any ignored reasoning
    prompt_messages = await thread_messages_to_prompt_messages(kernel, thread_messages, state)

    post_processed_messages = []
    for message in prompt_messages:
        # Only agent messages can have reasoning
        if not isinstance(message, PromptAgentMessage):
            post_processed_messages.append(message)
            continue

        new_content = []
        for content in message.content:
            # Only strip reasoning that we're explicitly ignoring
            if _should_ignore_reasoning(content):
                continue
            # Otherwise, keep the content
            new_content.append(content)

        # Reconstruct the message with the new content
        post_processed_messages.append(PromptAgentMessage(content=new_content))

    return post_processed_messages
