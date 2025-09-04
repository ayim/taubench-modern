"""
Default architecture for running agents.
"""

from importlib.metadata import version

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)

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
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
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
    while True:
        state.current_iteration += 1
        if state.current_iteration > MAX_ITERATIONS:
            state = await _handle_max_iterations(kernel, state)
            break

        # Process the conversation step
        if state.step in ("processing", "initial"):
            try:
                state = await _process_conversation_step(kernel, state)
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


async def _handle_max_iterations(kernel: Kernel, state: ArchState) -> ArchState:
    message = await kernel.thread_state.new_agent_message()
    message.append_thought(
        "I've reached my limit of iterations. By default, I'm limited to 25 "
        "autonomous iterations before requiring input from the user. I should "
        "let the user know that I've reached this limit and that, if they'd like "
        "to continue, they should just respond with 'continue'."
    )
    await message.stream_delta()
    message.append_content(
        "I've reached my iteration limit. By default, I'm limited to 25 "
        "autonomous iterations before requiring human input.\n\n```sema4-json\n"
        '{ "type": "quick-options", "data": [{"message": "continue", '
        '"title": "Continue", "iconName": "IconContinueIcon" }]}\n```'
    )
    await message.stream_delta()
    await message.commit()

    return state


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
async def _process_conversation_step(kernel: Kernel, state: ArchState) -> ArchState:  # noqa: C901, PLR0912, PLR0915
    # Register the thread message conversion function
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

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
    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(
        kernel.agent.mcp_servers,
    )

    # Note: leave this under a feature flag for now, as it's not ready for prime time yet.
    # Check if data frames are enabled via environment variable or agent settings
    enable_data_frames = kernel.data_frames.is_enabled()

    data_frames_tools: tuple[ToolDefinition, ...] = ()
    if enable_data_frames:
        await kernel.data_frames.step_initialize(state=state)
        data_frames_tools = kernel.data_frames.get_data_frame_tools()

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

    # And let's add the tools to the prompt
    conversation_prompt = conversation_prompt.with_tools(*tools)

    # Let's create a new message in the thread
    message = await kernel.thread_state.new_agent_message()

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

    # And use the formatted prompt, model, and message to receive a stream
    # of output from the model as it processes the conversation
    async with platform.stream_response(conversation_prompt, model) as stream:
        content_sink = message.sinks.content

        # Pipe the stream to the message
        await stream.pipe_to(
            # Sink thoughts / content / tool calls to message
            message.sinks.thoughts,
            message.sinks.tool_calls,
            content_sink,
            # Sink pending tool calls and step
            # to state (so we can execute tools later)
            state.sinks.pending_tool_calls,
            state.sinks.step,
        )

        # Add usage information to agent metadata if available
        if stream.reassembled_response and stream.reassembled_response.usage:
            usage = stream.reassembled_response.usage
            # Add to new multi-model tracking
            _add_model_usage_to_metadata(message, platform.name, model, usage, "main")
        else:
            # Even if no usage info, record that this model was used
            _add_model_usage_to_metadata(message, platform.name, model, None, "main")

        if stream.raw_response_matches(OUTPUT_FORMAT_REGEX):
            logger.info("Raw response matches output format regex")
        elif stream.raw_response_matches_with_postfix(
            OUTPUT_FORMAT_REGEX, "</response><step>processing</step></formatting>"
        ):
            # Okay, a model didn't close out the response, fine
            # we can force close the content sink and set the step
            # to processing
            await content_sink.force_close()
            state.step = "processing"
        elif stream.raw_response_matches_with_postfix(OUTPUT_FORMAT_REGEX, "</step></formatting>"):
            # Okay, we just left off the step and close formatting tag,
            # we can live with that with no issues
            pass
        elif stream.reassembled_response:
            # We have a response, it doesn't match the output format,
            # so we need to try and fix it
            state.agent_last_response_text = "\n".join(
                [text.text for text in stream.reassembled_response.content if text.kind == "text"]
            )
            state.agent_last_response_tools_str = "\n".join(
                [
                    f"{tool.tool_name}: {tool.tool_input_raw}"
                    for tool in stream.reassembled_response.content
                    if tool.kind == "tool_use"
                ]
            )

            state, message = await _backup_prompt_for_invalid_format(
                kernel,
                state,
                message,
                [*action_tools, *mcp_tools, *kernel.client_tools, *data_frames_tools],
            )
    # Update the message to show that the tool calls are running in the chat
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

    # Final commit - if we had tools, ignore websocket errors since tools might be long-running
    if state.called_tools:
        await message.commit(ignore_websocket_errors=True)
    else:
        # No tools were called, use normal commit
        await message.commit()

    return state


async def _backup_prompt_for_invalid_format(
    kernel: Kernel,
    state: ArchState,
    message: ThreadMessageWithThreadState,
    tools: list[ToolDefinition],
) -> tuple[ArchState, ThreadMessageWithThreadState]:
    # If we're here, we failed to follow the output format, but we _may_
    # have produced tool calls. Claude like to tool call and just trail off
    # not finishing the format
    unformatted_backup_prompt = select_prompt(
        prompt_paths=["prompts/fix-output"],
        package=__package__,
    )

    formatted_backup_prompt = await kernel.prompts.format_prompt(
        unformatted_backup_prompt,
        state=state,
    )

    # Some platforms (Cortex) require the tools to be added to the prompt
    # lest we get a 400 error
    formatted_backup_prompt = formatted_backup_prompt.with_tools(*tools)

    # Get a platform and it's default LLM
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    async with platform.stream_response(formatted_backup_prompt, model) as stream:
        # Reset message thoughts and content
        message.clear_thoughts()
        message.clear_content()
        await message.stream_delta()

        await stream.pipe_to(
            message.sinks.thoughts,
            message.sinks.content,
            state.sinks.step,
        )

        # Track backup prompt model usage
        if stream.reassembled_response and stream.reassembled_response.usage:
            _add_model_usage_to_metadata(
                message, platform.name, model, stream.reassembled_response.usage, "backup"
            )
        else:
            # Even if no usage info, record that this model was used for backup
            _add_model_usage_to_metadata(message, platform.name, model, None, "backup")

    return state, message
