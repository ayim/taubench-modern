import asyncio
import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from agent_platform.architectures.experimental.checkpoint import (
    CheckpointTxn,
    is_transient_stream_error,
)
from agent_platform.architectures.experimental.common import get_internal_tools
from agent_platform.architectures.experimental.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.agent_architectures.state import PendingToolCall
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.selector.default import select_prompt
from agent_platform.core.responses.streaming.stream_pipe import ResponseStreamPipe
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.tools.tool_execution_result import ToolExecutionResult

logger = logging.getLogger(__name__)

# ---- Architecture knobs -------------------------------------------------------

MAX_ITERATIONS = 25

# If the model emits no tool calls, we nudge it (controller feedback) up to:
NO_TOOLCALL_RETRY_LIMIT = 3

# For the final reply step, how many times we allow "no text" before fail-open:
NO_FINAL_REPLY_RETRY_LIMIT = 3

# Model tool names that terminate the processing loop:
TERMINAL_TOOLS = {"ready_to_reply_to_user", "unable_to_satisfy_request", "quick_reply"}

# Stream retry knobs for *transient* mid-stream failures (e.g., broken SSE)
STREAM_RETRY_MAX = 3
STREAM_BACKOFF_SECONDS = (0.6, 1.5, 3.0)  # simple backoff per attempt


# ---- State --------------------------------------------------------------------


class Exp1State(aa.StateBase):
    """
    State for Experimental Architecture 1.

    Fields here are used both for prompt formatting (controller feedback, etc.)
    and for execution bookkeeping (iteration counts, retries).
    """

    current_iteration: int
    processing_start_time: str
    no_toolcall_retry_count: int
    no_final_reply_retry_count: int
    controller_feedback: str
    configuration_issues: list[str]
    step: Literal["initial", "processing", "done"]
    processing_elapsed_time: str
    recently_called_tools: list[ToolExecutionResult]
    tool_loop_detected: bool = False
    callable_tools_summary: str = ""
    data_frames_tools_state: Literal["enabled", ""] = ""
    memories: list[str] = field(default_factory=list, metadata=aa.fields.thread_scoped())

    @property
    def sinks(self):
        """Expose sinks for agent-arch -> state (e.g., pending tool-calls)."""
        return self.Sinks(self)


# ---- Helpers & Data Structures ------------------------------------------------


@dataclass(frozen=True)
class ToolsBundle:
    """All tools we attach to prompts this turn."""

    action_tools: Sequence[ToolDefinition]
    mcp_tools: Sequence[ToolDefinition]
    client_tools: Sequence[ToolDefinition]
    internal_tools: Sequence[ToolDefinition]
    data_frames_tools: Sequence[ToolDefinition]

    @property
    def all(self) -> tuple[ToolDefinition, ...]:
        """Flattened sequence for prompt.with_tools(*bundle.all)."""
        return (
            *self.action_tools,
            *self.mcp_tools,
            *self.client_tools,
            *self.internal_tools,
            *self.data_frames_tools,
        )


# ---- Entry Point --------------------------------------------------------------


@aa.entrypoint
async def entrypoint_exp_1(kernel: Kernel, state: Exp1State) -> Exp1State:
    """
    Top-level entrypoint. Initializes state and runs the processing pipeline.
    """
    try:
        logger.info("Experimental architecture 1 starting")
        _initialize_state_for_run(state)
        return await _process_conversation_step(kernel, state)
    except Exception:
        logger.error("Experimental architecture 1 failed", exc_info=True)
        raise
    finally:
        logger.info("Experimental architecture 1 completed")


# ---- Main Step ---------------------------------------------------------------


@aa.step
async def _process_conversation_step(kernel: Kernel, state: Exp1State) -> Exp1State:
    """
    The main multi-iteration tool loop + final-reply flow.

    High-level flow:
      1) Gather tools and platform/model.
      2) Loop up to MAX_ITERATIONS:
         - Build tool-loop prompt
         - Stream with checkpoint+retry (deltas ASAP)
         - If no tool calls, nudge & retry; else execute tool calls
         - Respect TERMINAL_TOOLS / quick_reply early exit
      3) If still not 'done', produce final reply (with its own checkpoint+retry)
      4) Commit the message
    """
    # Convert thread messages to prompt messages for this architecture
    kernel.converters.set_thread_message_conversion_function(thread_messages_to_prompt_messages)

    # Initialize data frame tooling (if any)
    await kernel.data_frames.step_initialize(state=state)

    # Tools and configuration checks
    tools, issues = await _gather_tools(kernel, state)
    state.configuration_issues = issues

    # Platform/model & family
    platform, model, model_family = await _resolve_platform_and_model(kernel)

    # Create the output message we stream into
    message = await kernel.thread_state.new_agent_message(
        tag_expected_past_response=None,
        tag_expected_pre_response=None,
    )
    message.agent_metadata["models"] = []

    # -------------------- Tool Loop --------------------
    while state.step != "done" and state.current_iteration < MAX_ITERATIONS:
        state.current_iteration += 1
        _update_elapsed_time(state)

        logger.info(f"Iteration {state.current_iteration}/{MAX_ITERATIONS} (model={model})")
        logger.debug(
            f"Controller feedback (pre-iteration): {state.controller_feedback or '<none>'}"
        )

        # Build the tool-loop prompt
        conversation_prompt = await _build_tool_loop_prompt(
            kernel=kernel,
            model_family=model_family,
            state=state,
            tools=tools,
        )

        # Stream with checkpoint+retry to real sinks (deltas go out ASAP)
        await _stream_tool_loop_with_retry(
            platform=platform,
            model=model,
            prompt=conversation_prompt,
            message=message,
            state=state,
        )

        # Decide next step based on pending tool calls
        pending = list(state.pending_tool_calls)
        if not pending:
            if await _handle_no_tool_calls(state):
                continue
            else:
                break

        # Reset counters once we *do* see tool calls
        state.no_toolcall_retry_count = 0
        state.controller_feedback = ""

        # Mark tools as running in the UI and detect terminal tools
        saw_quick_reply = await _mark_tools_running_and_detect_terminal(
            message=message,
            pending_tool_calls=state.pending_tool_calls,
            terminal_tools=TERMINAL_TOOLS,
            state=state,
        )

        # Execute tool calls (emits its own deltas)
        await _execute_pending_tools(kernel, state, message)

        # If quick_reply was issued, we're done with the turn—commit and exit.
        if saw_quick_reply:
            logger.info("quick_reply issued; committing message.")
            await message.commit()
            return state

    # Iteration cap reached --> explain and offer to continue
    if state.current_iteration >= MAX_ITERATIONS:
        state.step = "done"
        _append_iteration_limit_note(message)
        await message.stream_delta()
        await message.commit()
        return state

    # -------------------- Final Reply --------------------
    final_prompt = await _build_final_reply_prompt(
        kernel=kernel,
        model_family=model_family,
        state=state,
        tools=tools,
    )

    has_final_reply = False
    while not has_final_reply:
        logger.info(f"Producing final reply (attempt {state.no_final_reply_retry_count + 1})")

        # Stream with checkpoint+retry (reasoning + raw text)
        stream = await _stream_final_reply_with_retry(
            platform=platform,
            model=model,
            prompt=final_prompt,
            message=message,
            state=state,
        )

        # Determine if we got a non-empty text reply
        has_final_reply = _has_text_content(stream)
        if not has_final_reply:
            if not await _handle_no_final_reply(state, message):
                break

    # Commit thread message and finish
    logger.info("Final reply completed; committing message.")
    await message.commit()
    return state


# ---- Small, Focused Helpers ---------------------------------------------------


def _initialize_state_for_run(state: Exp1State) -> None:
    """Initialize/clear per-run fields."""
    state.step = "initial"
    state.configuration_issues = []
    state.current_iteration = 0
    state.no_toolcall_retry_count = 0
    state.no_final_reply_retry_count = 0
    state.controller_feedback = ""
    state.processing_start_time = datetime.now(UTC).isoformat(timespec="milliseconds")
    state.processing_elapsed_time = "0.00 seconds"
    state.recently_called_tools = []
    state.tool_loop_detected = False
    state.callable_tools_summary = ""
    state.memories = []


async def _gather_tools(kernel: Kernel, state: Exp1State) -> tuple[ToolsBundle, list[str]]:
    """
    Gather tools from action packages, MCP servers, client, internal, and data-frame tools.
    Returns:
        (ToolsBundle, configuration_issues)
    """
    data_frames_tools = kernel.data_frames.get_data_frame_tools()

    action_tools, action_issues = await kernel.tools.from_action_packages(
        kernel.agent.action_packages
    )
    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(kernel.agent.mcp_servers)
    internal = get_internal_tools(kernel, state)
    client = kernel.client_tools

    issues = [*action_issues, *mcp_issues]

    logger.info(
        f"Tools gathered: action={len(action_tools)}, "
        f"mcp={len(mcp_tools)}, "
        f"client={len(client)}, "
        f"internal={len(internal)}, "
        f"data_frames={len(data_frames_tools)}",
    )
    if issues:
        logger.info(f"Tool issues: {', '.join(issues)}")

    state.callable_tools_summary = ""
    source_tool_zip = zip(
        ("sema4ai-actions", "mcp-server", "client-tool", "internal-tool", "data-frame-tool"),
        (action_tools, mcp_tools, client, internal, data_frames_tools),
        strict=True,
    )
    for tool_idx, (source, tools) in enumerate(source_tool_zip):
        for tool in tools:
            state.callable_tools_summary += (
                f"<tool index='{tool_idx + 1}' source='{source}'>{tool.name}</tool>\n"
            )
    state.callable_tools_summary = state.callable_tools_summary.strip()

    return ToolsBundle(
        action_tools=action_tools,
        mcp_tools=mcp_tools,
        client_tools=client,
        internal_tools=internal,
        data_frames_tools=data_frames_tools,
    ), issues


async def _resolve_platform_and_model(kernel: Kernel):
    """
    Resolve platform and default LLM model, plus the optional model family.
    """
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    try:
        model_family = platform.client.model_map.model_families.get(model)
    except (AttributeError, KeyError):
        logger.warning(f"Model family not found for model: {model}")
        model_family = None

    logger.info(f"Using model: {model} (family={model_family})")
    return platform, model, model_family


async def _build_tool_loop_prompt(
    kernel: Kernel,
    model_family: str | None,
    state: Exp1State,
    tools: ToolsBundle,
):
    """Select and format the tool-loop prompt, attach tools."""
    tmpl = select_prompt(
        prompt_paths=["prompts/tool-loop"],
        package=__package__,
        model_family=model_family,
    )
    prompt = await kernel.prompts.format_prompt(tmpl, state=state)
    prompt = prompt.with_tools(*tools.all)
    return prompt


async def _build_final_reply_prompt(
    kernel: Kernel,
    model_family: str | None,
    state: Exp1State,
    tools: ToolsBundle,
):
    """Select and format the final-reply prompt, attach tools, minimize reasoning."""
    tmpl = select_prompt(
        prompt_paths=["prompts/final-reply"],
        package=__package__,
        model_family=model_family,
    )
    prompt = await kernel.prompts.format_prompt(tmpl, state=state)
    prompt = prompt.with_tools(*tools.all).with_minimized_reasoning()
    return prompt


def _update_elapsed_time(state: Exp1State) -> None:
    """Update elapsed time string on state (for prompt visibility & logs)."""
    elapsed_seconds = (
        datetime.now(UTC) - datetime.fromisoformat(state.processing_start_time)
    ).total_seconds()
    state.processing_elapsed_time = f"{elapsed_seconds:.2f} seconds"


async def _stream_tool_loop_with_retry(
    platform: PlatformInterface,
    model: str,
    prompt: Prompt,
    message: ThreadMessageWithThreadState,
    state: Exp1State,
) -> None:
    """
    Stream the tool-loop turn with checkpoint+retry.

    Sends deltas immediately to the client's sinks.
    On transient mid-stream failure, rolls back to the checkpoint and retries.
    """
    message.mark_prompt_start()

    attempt = 0
    while True:
        attempt += 1
        ckpt = CheckpointTxn(message, state)
        logger.info(f"Streaming tool-loop (attempt {attempt}/{STREAM_RETRY_MAX})")

        try:
            async with platform.stream_response(prompt, model) as stream:
                await stream.pipe_to(
                    message.sinks.reasoning,
                    message.sinks.tool_calls(
                        forward_to_content="quick_reply",
                        content_from_key="markdown",
                    ),
                    message.sinks.usage,
                    state.sinks.pending_tool_calls,
                )
            # Success
            ckpt.commit()
            message.mark_prompt_end()
            message.agent_metadata["models"].append(
                {
                    "platform": platform.name,
                    "model": model,
                    "call_type": "tool-loop",
                    "usage": (
                        stream.reassembled_response.usage.model_dump()
                        if stream.reassembled_response and stream.reassembled_response.usage
                        else None
                    ),
                }
            )
            logger.info(f"Tool-loop stream complete (attempt {attempt}).")
            return

        except Exception as e:
            transient = is_transient_stream_error(e)
            can_retry = transient and attempt < STREAM_RETRY_MAX

            if can_retry:
                logger.warning(
                    "Transient stream failure during tool-loop "
                    f"(attempt {attempt}/{STREAM_RETRY_MAX}): {e}"
                )
                await ckpt.rollback()
                await asyncio.sleep(
                    STREAM_BACKOFF_SECONDS[min(attempt - 1, len(STREAM_BACKOFF_SECONDS) - 1)]
                )
                continue

            # Final failure: rollback and re-raise
            logger.error(f"Tool-loop stream failed (non-retryable or exhausted): {e}")
            await ckpt.rollback()
            raise


async def _mark_tools_running_and_detect_terminal(
    message: ThreadMessageWithThreadState,
    pending_tool_calls: Iterable[PendingToolCall],
    terminal_tools: set[str],
    state: Exp1State,
) -> bool:
    """
    Update UI to show tools 'running', detect TERMINAL_TOOLS, and emit deltas.
    Returns:
        True if 'quick_reply' was among the tool calls.
    """
    saw_quick_reply = False
    pending_list = list(pending_tool_calls)

    logger.info(f"Pending tool calls: {len(pending_list)}")
    logger.debug(f"Pending tool call IDs: {', '.join([tc.tool_call_id for _, tc in pending_list])}")

    for _, tool_call in pending_list:
        message.update_tool_running(tool_call.tool_call_id)

        if tool_call.tool_name in terminal_tools:
            state.step = "done"
        if tool_call.tool_name == "quick_reply":
            saw_quick_reply = True

        await message.stream_delta()

    return saw_quick_reply


async def _execute_pending_tools(
    kernel: Kernel,
    state: Exp1State,
    message: ThreadMessageWithThreadState,
) -> None:
    """Execute all pending tool calls and update the message as results arrive."""

    most_recent_tools = []
    async for result in kernel.tools.execute_pending_tool_calls(
        state.pending_tool_calls,
        message,
    ):
        most_recent_tools.append(result)
        result_key = _tool_execution_name_and_input_key(result)
        for recent in state.recently_called_tools:
            recent_key = _tool_execution_name_and_input_key(recent)
            if result_key != recent_key:
                continue
            if _tool_execution_output_key(result) == _tool_execution_output_key(recent):
                result.inject_system_feedback(
                    "You've already called this tool with this same input, and it's "
                    "output remains the same. Unless this behavior is intentional "
                    "(specified in your Runbook or explicitly requested by the user), "
                    "you should not call this tool again with the same input."
                )
                message.update_tool_result(result)
                await message.stream_delta()
                break

    # Try and detect repeated calls to the same tool
    # If the most recent tools intersect with the 5 previous tool
    # calls, then let's warn the agent
    last_5_as_set = {
        _tool_execution_name_and_input_key(result) for result in state.recently_called_tools[-5:]
    }
    most_recent_as_set = {
        _tool_execution_name_and_input_key(result) for result in most_recent_tools
    }
    if most_recent_as_set & last_5_as_set:
        state.controller_feedback += (
            "TOOL LOOP WARNING: You seem to be calling the same tool with the same arguments, "
            "it's possible this makes sense, but also unlikely without strong justification. "
            "Consider carefully if you are looping unnecessarily!"
        )
        state.tool_loop_detected = True
    else:
        state.tool_loop_detected = False

    state.recently_called_tools.extend(most_recent_tools)
    # Only keep the last 20 tool calls in "most recent" list to avoid bloating
    state.recently_called_tools = state.recently_called_tools[-20:]


async def _handle_no_tool_calls(state: Exp1State) -> bool:
    state.no_toolcall_retry_count += 1
    if state.no_toolcall_retry_count <= NO_TOOLCALL_RETRY_LIMIT:
        state.controller_feedback = (
            "No tool calls were detected in the last turn. "
            "This is a TOOL-ONLY turn. Call at least one tool. "
            "If you are done, call ready_to_reply_to_user. "
            "If you are unable to satisfy the request, call unable_to_satisfy_request. "
            "Do not emit any prose."
        )
        logger.info(
            "No tool calls detected; nudging model "
            f"(retry {state.no_toolcall_retry_count}/{NO_TOOLCALL_RETRY_LIMIT})."
        )
        return True
    else:
        # Fail-open to avoid stalls; we'll do a final reply next.
        logger.info("No tool calls after retries; moving to final reply.")
        state.step = "done"
        state.controller_feedback = ""
        return False


def _append_iteration_limit_note(message: ThreadMessageWithThreadState) -> None:
    """Append an iteration-limit explanation with a 'Continue' quick-option."""
    message.append_content(
        f"I've reached my iteration limit. By default, I'm limited to {MAX_ITERATIONS} "
        "autonomous iterations before requiring human input.\n\n```sema4-json\n"
        '{ "type": "quick-options", "data": [{"message": "continue", '
        '"title": "Continue", "iconName": "IconContinueIcon" }]}\n```',
        complete=True,
    )


async def _stream_final_reply_with_retry(
    platform: PlatformInterface,
    model: str,
    prompt: Prompt,
    message: ThreadMessageWithThreadState,
    state: Exp1State,
):
    """
    Stream the final reply turn with checkpoint+retry.

    Returns:
        The 'stream' object from platform.stream_response (...) so the caller
        can inspect reassembled_response for text presence.
    """
    message.mark_prompt_start()

    attempt = 0
    stream = None
    while True:
        attempt += 1
        ckpt = CheckpointTxn(message, state)
        logger.info(f"Streaming final reply (attempt {attempt}/{STREAM_RETRY_MAX})")

        try:
            async with platform.stream_response(prompt, model) as s:
                stream = s  # capture for caller's inspection
                await s.pipe_to(
                    message.sinks.reasoning,
                    message.sinks.raw_content,
                    message.sinks.usage,
                )
            # Success
            ckpt.commit()
            message.mark_prompt_end()
            message.agent_metadata["models"].append(
                {
                    "platform": platform.name,
                    "model": model,
                    "call_type": "final-reply",
                    "usage": (
                        stream.reassembled_response.usage.model_dump()
                        if stream.reassembled_response and stream.reassembled_response.usage
                        else None
                    ),
                }
            )
            logger.info(f"Final-reply stream complete (attempt {attempt}).")
            return stream

        except Exception as e:
            transient = is_transient_stream_error(e)
            can_retry = transient and attempt < STREAM_RETRY_MAX

            if can_retry:
                logger.warning(
                    "Transient stream failure during final reply "
                    f"(attempt {attempt}/{STREAM_RETRY_MAX}): {e}"
                )
                await ckpt.rollback()
                await asyncio.sleep(
                    STREAM_BACKOFF_SECONDS[min(attempt - 1, len(STREAM_BACKOFF_SECONDS) - 1)]
                )
                continue

            logger.error(f"Final-reply stream failed (non-retryable or exhausted): {e}")
            await ckpt.rollback()
            raise


def _has_text_content(stream: ResponseStreamPipe) -> bool:
    """
    Determine if the final reply produced any non-empty text.
    Uses stream.reassembled_response.content when available.
    """
    try:
        content = getattr(getattr(stream, "reassembled_response", None), "content", None)
        if not content:
            return False
        return any(
            getattr(c, "kind", None) == "text" and getattr(c, "text", "").strip() for c in content
        )
    except Exception:
        # If we cannot inspect, be conservative
        return False


async def _handle_no_final_reply(
    state: Exp1State,
    message: ThreadMessageWithThreadState,
) -> bool:
    state.no_final_reply_retry_count += 1
    if state.no_final_reply_retry_count <= NO_FINAL_REPLY_RETRY_LIMIT:
        state.controller_feedback = (
            "Tool calls were detected in the final reply. "
            "This is a FINAL-REPLY-ONLY turn. All tool calls will be ignored. "
            "Please provide a text-only final reply, according to your instructions. "
        )
        logger.info(
            f"Final reply contained no text or attempted tool use; retrying "
            f"({state.no_final_reply_retry_count}/{NO_FINAL_REPLY_RETRY_LIMIT})."
        )
        return True
    else:
        logger.info("No final reply after retries; failing open with placeholder.")
        state.step = "done"
        state.controller_feedback = ""
        message.append_content("No final reply was provided.", complete=True)
        await message.stream_delta()
        await message.commit()
        return False


def _tool_execution_name_and_input_key(result: ToolExecutionResult) -> str:
    canonical_args = json.dumps(result.input, sort_keys=True)
    return f"{result.definition.name}({canonical_args})"


def _tool_execution_output_key(result: ToolExecutionResult) -> str:
    return json.dumps(result.output_raw, sort_keys=True)
