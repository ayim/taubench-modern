"""
Default architecture for running agents.
"""

from importlib.metadata import version
from typing import TYPE_CHECKING

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.agent_architectures.special_commands import (
    handle_special_command,
    parse_special_command,
)
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.mcp.mcp_server import MCPServer

if TYPE_CHECKING:
    from agent_platform.server.storage.base import BaseStorage

__author__ = "Sema4.ai Engineering"
__copyright__ = "Copyright 2025, Sema4.ai"
__license__ = "Proprietary"
__summary__ = "Default architecture for the Agent Platform"
__version__ = version("agent_platform_architectures_default")

import logging
import re
from datetime import UTC, datetime

from agent_platform.architectures.default.state import ArchState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.prompts import select_prompt
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)

MAX_STATE_PARSE_FAILURE_COUNT = 3
MAX_ITERATIONS = 25
# Odd behavior seen in the wild: empty responses.
# Let's make this regex a tad more strict.
OUTPUT_FORMAT_REGEX = re.compile(
    r"^\s*<formatting>\s*<thinking>.*\S.*</thinking>\s*<response>.*\S.*</response>\s*<step>.*\S.*</step>\s*</formatting>\s*$",
    re.DOTALL,
)

# Let's create a new global message for the agent thread
message = None


def _add_model_usage_to_metadata(
    message, platform_name: str, model: str, usage_info=None, call_type: str = "main"
):
    """Add model usage information to the message metadata.

    Args:
        message: The ThreadMessage to update
        platform_name: Name of the platform used
        model: Model identifier used
        usage_info: Usage statistics from the stream response
        call_type: Type of call ('main' or 'backup')
    """
    model_entry = {
        "platform": platform_name,
        "model": model,
        "call_type": call_type,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
        },
    }

    if usage_info:
        model_entry["usage"].update(
            {
                "input_tokens": usage_info.input_tokens or 0,
                "output_tokens": usage_info.output_tokens or 0,
                "total_tokens": usage_info.total_tokens or 0,
                "cached_tokens": usage_info.cached_tokens or 0,
                "reasoning_tokens": usage_info.reasoning_tokens or 0,
            }
        )

        # Update total usage
        total_usage = message.agent_metadata["total_usage"]
        total_usage["input_tokens"] += model_entry["usage"]["input_tokens"]
        total_usage["output_tokens"] += model_entry["usage"]["output_tokens"]
        total_usage["total_tokens"] += model_entry["usage"]["total_tokens"]
        total_usage["cached_tokens"] += model_entry["usage"]["cached_tokens"]
        total_usage["reasoning_tokens"] += model_entry["usage"]["reasoning_tokens"]

    message.agent_metadata["models"].append(model_entry)


@aa.entrypoint
async def entrypoint(kernel: Kernel, state: ArchState) -> ArchState:
    state.current_iteration = 0
    state.processing_start_time = datetime.now(UTC).isoformat(
        timespec="milliseconds",
    )
    message = (
        await kernel.thread_state.new_agent_message()
    )  # Create a new message for this entrypoint

    while True:
        state.current_iteration += 1
        if state.current_iteration > MAX_ITERATIONS:
            state = await _handle_max_iterations(state, message)
            break

        # Process the conversation step
        if state.step in ("processing", "initial"):
            try:
                state = await _process_conversation_step(kernel, state, message)
            except Exception as e:
                logger.error(
                    "Error processing conversation step: %s",
                    e,
                )
                raise e
        elif state.step == "done":
            break
        else:
            state = await _handle_state_parse_failure(kernel, state)

    return state


async def _commit_message(message: ThreadMessageWithThreadState, state: ArchState):
    """Commit the message, ignoring websocket errors if tools were called."""
    if state.called_tools:
        # If we had tools, ignore websocket errors since tools might be long-running
        await message.commit(ignore_websocket_errors=True)
    else:
        # No tools were called, use normal commit
        await message.commit()


async def _handle_max_iterations(
    state: ArchState, message: ThreadMessageWithThreadState
) -> ArchState:
    """Append iteration-limit notice to the current turn message and commit it."""

    # Add the user-facing content with a quick-option to continue
    message.append_content(
        "I've reached my iteration limit. By default, I'm limited to 25 "
        "autonomous iterations before requiring human input.\n\n```sema4-json\n"
        '{ "type": "quick-options", "data": [{"message": "continue", '
        '"title": "Continue", "iconName": "IconContinueIcon" }]}\n```'
    )
    await message.stream_delta()

    # Commit with long-running tools behavior
    await _commit_message(message, state)

    return state


async def _resolve_global_mcp_servers(kernel: Kernel) -> list[MCPServer]:
    """Resolve global MCP servers from their IDs."""
    global_mcp_server_ids = kernel.agent.mcp_server_ids
    if not global_mcp_server_ids:
        return []

    storage: BaseStorage = kernel.storage._internal_storage  # type: ignore
    mcp_servers_dict = await storage.get_mcp_servers_by_ids(global_mcp_server_ids)
    return list(mcp_servers_dict.values())


async def _handle_state_parse_failure(kernel: Kernel, state: ArchState) -> ArchState:
    # Update our state to reflect the failure
    state.state_parse_failure_count += 1
    state.last_step_issues = [
        "We failed to parse the step from the output format. "
        "Remember, you must always include a <step>...</step> tag "
        "in your output so we know what to do next. The valid "
        "values are 'processing' and 'done'."
    ]

    # If we're continuing to fail, let the user know we're having some issues
    if state.state_parse_failure_count > MAX_STATE_PARSE_FAILURE_COUNT:
        message = await kernel.thread_state.new_agent_message()
        message.append_thought(
            "I've reached my limit of attempts to parse the output format. I should "
            "let the user know that I'm having some trouble following the correct "
            "output format and ask them to create a new thread if the issue persists."
        )
        await message.stream_delta()
        message.append_content(
            "I'm sorry, I'm having some trouble following the correct output format.\n"
            "Please try again and, if the issue persists, create a new thread."
        )
        await message.stream_delta()
        await message.commit()
        state.step = "done"  # We're done now, too many failures

    return state


@aa.step
async def _process_conversation_step(  # noqa: C901, PLR0912, PLR0915
    kernel: Kernel, state: ArchState, message: ThreadMessageWithThreadState
) -> ArchState:
    # Register the thread message conversion function
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

    # Special commands hook (e.g., /debug, /help, /toggle, /set, /unset)
    latest_text = kernel.thread.latest_user_message_as_text
    cmd = parse_special_command(latest_text)
    if cmd is not None:
        handled = await handle_special_command(cmd, kernel, state=state)
        if handled:
            state.step = "done"
            return state

    # Update the elapsed time
    elapsed_seconds = (
        datetime.now(UTC) - datetime.fromisoformat(state.processing_start_time)
    ).total_seconds()
    state.processing_elapsed_time = f"{elapsed_seconds:.2f} seconds"

    # First, let's attempt to get any relevant tools from
    # our action packages and MCP servers
    action_tools, action_issues = await kernel.tools.from_action_packages(
        kernel.agent.action_packages,
    )

    global_mcp_servers = await _resolve_global_mcp_servers(kernel)
    all_mcp_servers = [*global_mcp_servers, *kernel.agent.mcp_servers]

    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(
        all_mcp_servers,
    )

    # Note: leave this under a feature flag for now, as it's not ready for prime time yet.
    # Check if data frames are enabled via environment variable or agent settings
    enable_data_frames = kernel.data_frames.is_enabled()

    data_frames_tools: tuple[ToolDefinition, ...] = ()
    if enable_data_frames:
        await kernel.data_frames.step_initialize(state=state)
        data_frames_tools = kernel.data_frames.get_data_frame_tools()

    enable_work_item = kernel.work_item.is_enabled()
    work_item_tools: tuple[ToolDefinition, ...] = ()
    if enable_work_item:
        await kernel.work_item.step_initialize(state=state)
        work_item_tools = kernel.work_item.get_work_item_tools()

    # Save any issues to state for introspection
    state.configuration_issues = [*action_issues, *mcp_issues]

    # Get a platform and it's default LLM
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    # Get the family of the chosen model
    try:
        # We're making this more careful as we transition some model platform
        # client internals... (and we don't _actually_ use the prompt
        # specialization today)
        model_family = platform.client.model_map.model_families.get(model)
    except (AttributeError, KeyError):
        logger.warning("Model family not found for model: %s", model)
        model_family = None

    # Select and load the prompt we'll be using
    unformatted_conversation_prompt = select_prompt(
        prompt_paths=["prompts/default"],
        package=__package__,
        model_family=model_family,
    )

    # Format the prompt
    conversation_prompt = await kernel.prompts.format_prompt(
        unformatted_conversation_prompt,
        state=state,
    )

    tools: list[ToolDefinition] = action_tools + mcp_tools + kernel.client_tools
    tools.extend(data_frames_tools)
    tools.extend(work_item_tools)

    # And let's add the tools to the prompt
    conversation_prompt = conversation_prompt.with_tools(*tools)

    message.agent_metadata["platform"] = platform.name
    message.agent_metadata["model"] = model  # Keep for backward compatibility
    message.agent_metadata["tools"] = [tool.model_dump() for tool in tools]

    # Initialize new multi-model tracking structure
    message.agent_metadata["models"] = []
    message.agent_metadata["total_usage"] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }

    await message.stream_delta()

    # And use the formatted prompt, model, and message to receive a stream
    # of output from the model as it processes the conversation
    async with platform.stream_response(conversation_prompt, model) as stream:
        # Pipe thinking, tool calls, and step (no early user-visible content)
        await stream.pipe_to(
            message.sinks.stop_reason_guard,
            message.sinks.thoughts,
            message.sinks.tool_calls(),
            state.sinks.pending_tool_calls,
            state.sinks.step,
        )

        # Safely get usage info and add it to metadata if available, or add none if none
        usage = getattr(getattr(stream, "reassembled_response", None), "usage", None)
        _add_model_usage_to_metadata(message, platform.name, model, usage, "main")

        if stream.raw_response_matches(OUTPUT_FORMAT_REGEX):
            logger.info("Raw response matches output format regex")
        elif stream.raw_response_matches_with_postfix(
            OUTPUT_FORMAT_REGEX, "</response><step>processing</step></formatting>"
        ):
            # The model omitted some closing tags; treat as processing and continue.
            state.step = "processing"
        elif stream.raw_response_matches_with_postfix(OUTPUT_FORMAT_REGEX, "</step></formatting>"):
            # Missing only trailing tags; no action required.
            pass

    # UI updates for pending tool calls (tool statuses are streamed live)
    await message.stream_delta()
    for _, tool_call in state.pending_tool_calls:
        message.update_tool_running(tool_call.tool_call_id)
        await message.stream_delta()

    # If we have pending tool calls, do a soft commit first to persist the message
    # This allows tools to continue running even if websocket connection is lost
    if state.pending_tool_calls:
        await message.soft_commit()

    # Execute any pending tool calls and update the message
    async for _ in kernel.tools.execute_pending_tool_calls(
        state.pending_tool_calls,
        message,
    ):
        state.called_tools = True

    # If the model indicated it's ready to reply, produce a final reply now.
    if state.step == "done":
        try:
            # Curated status before final user-facing reply
            message.new_thought("Synthesizing final answer…", complete=True)
            await message.stream_delta()

            # Following the experimental architecture final-reply prompt pattern in default
            final_unformatted_prompt = select_prompt(
                prompt_paths=["prompts/final-reply"],
                package="agent_platform.architectures.default",
                model_family=model_family,
            )
            final_prompt = await kernel.prompts.format_prompt(
                final_unformatted_prompt,
                state=state,
            )
            final_prompt = final_prompt.with_tools(*tools).with_minimized_reasoning()

            async with platform.stream_response(final_prompt, model) as final_stream:
                # Stream the response content
                await final_stream.pipe_to(
                    message.sinks.stop_reason_guard,
                    message.sinks.raw_content,
                )

                # Get the reassembled response once; it may be None
                reassembled_response = final_stream.reassembled_response

                # Safely get usage info and add it to metadata
                usage = getattr(reassembled_response, "usage", None)
                _add_model_usage_to_metadata(message, platform.name, model, usage, "final-reply")

                # get the content list, defaulting to an empty list
                content = getattr(reassembled_response, "content", []) or []

                # Check for any non-empty text in the reassembled response
                has_reassembled_text = any(
                    getattr(part, "kind", "") == "text" and getattr(part, "text", "").strip()
                    for part in content
                )

                # If no text found in the reassembled response, append a default reply
                if not has_reassembled_text:
                    message.append_content("No final reply was provided.")
                    await message.stream_delta()
        except StreamingError:
            logger.error("Final reply generation failed", exc_info=True)
            raise
        except Exception:
            logger.error("Final reply generation failed", exc_info=True)

        # Final commit
        await _commit_message(message, state)

    return state
