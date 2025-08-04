import logging
from datetime import UTC, datetime

from agent_platform.architectures.default.state import ArchState
from agent_platform.architectures.experimental.common import (
    get_internal_tools,
)
from agent_platform.architectures.experimental.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.prompts.selector.default import select_prompt

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 25


class Exp1State(ArchState):
    current_iteration: int
    processing_start_time: str


@aa.entrypoint
async def entrypoint_exp_1(kernel: Kernel, state: ArchState) -> ArchState:
    try:
        logger.info("Running experimental architecture 1")
        state.current_iteration = 0
        state.processing_start_time = datetime.now(UTC).isoformat(
            timespec="milliseconds",
        )
        state = await _process_conversation_step(kernel, state)
        return state
    except Exception as e:
        logger.error("Error running experimental architecture 1", exc_info=True)
        raise e
    finally:
        logger.info("Experimental architecture 1 completed")


@aa.step
async def _process_conversation_step(kernel: Kernel, state: ArchState) -> ArchState:
    # Register the thread message conversion function
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

    # First, let's attempt to get any relevant tools from
    # our action packages and MCP servers
    action_tools, action_issues = await kernel.tools.from_action_packages(
        kernel.agent.action_packages,
    )
    # Get resolved MCP servers using the kernel's resolution method
    # resolved_mcp_servers = await kernel.get_resolved_mcp_servers()
    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(
        kernel.agent.mcp_servers,
    )
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

    # Let's create a new message in the thread
    message = await kernel.thread_state.new_agent_message(
        tag_expected_past_response=None,
        tag_expected_pre_response=None,
    )
    message.append_thought("I'm starting to process the user's request.")
    await message.stream_delta()

    # And use the formatted prompt, model, and message to receive a stream
    # of output from the model as it processes the conversation
    while state.step != "done" and state.current_iteration < MAX_ITERATIONS:
        state.current_iteration += 1

        # Update the elapsed time
        elapsed_seconds = (
            datetime.now(UTC) - datetime.fromisoformat(state.processing_start_time)
        ).total_seconds()
        state.processing_elapsed_time = f"{elapsed_seconds:.2f} seconds"

        # Select and load the prompt we'll be using
        unformatted_conversation_prompt = select_prompt(
            prompt_paths=["prompts/tool-loop"],
            package=__package__,
            model_family=model_family,
        )

        # Format the prompt
        conversation_prompt = await kernel.prompts.format_prompt(
            unformatted_conversation_prompt,
            state=state,
        )

        # And let's add the tools to the prompt
        conversation_prompt = conversation_prompt.with_tools(
            *action_tools,
            *mcp_tools,
            *kernel.client_tools,
            *get_internal_tools(),
        )

        async with platform.stream_response(conversation_prompt, model) as stream:
            await stream.pipe_to(
                message.sinks.tool_calls,
                state.sinks.pending_tool_calls,
            )

        # Extract out the thought tool calls
        thoughts = [
            tool_call.tool_input.get("thought", "")
            for tool_def, tool_call in state.pending_tool_calls
            if tool_def.name == "think" and tool_call.tool_input.get("thought", "")
        ]
        for thought in thoughts:
            message.new_thought(thought)
            await message.stream_delta()

        # Remove the thought tool calls from the pending tool calls
        state.pending_tool_calls = [
            (tool_def, tool_call)
            for tool_def, tool_call in state.pending_tool_calls
            if tool_def.name != "think"
        ]

        # Update the message to show that the tool calls are running in the chat
        for _, tool_call in state.pending_tool_calls:
            message.update_tool_running(tool_call.tool_call_id)
            if tool_call.tool_name == "unable_to_satisfy_request":
                state.step = "done"
            elif tool_call.tool_name == "ready_to_reply_to_user":
                state.step = "done"
            await message.stream_delta()

        # Execute any pending tool calls and update the message
        async for _ in kernel.tools.execute_pending_tool_calls(
            state.pending_tool_calls,
            message,
        ):
            pass

    if state.current_iteration >= MAX_ITERATIONS:
        state.step = "done"
        message.append_content(
            "I've reached my iteration limit. By default, I'm limited to 25 "
            "autonomous iterations before requiring human input.\n\n```sema4-json\n"
            '{ "type": "quick-options", "data": [{"message": "continue", '
            '"title": "Continue", "iconName": "IconContinueIcon" }]}\n```',
            complete=True,
        )
        await message.stream_delta()

    # Select and load the prompt we'll be using
    final_reply_prompt = select_prompt(
        prompt_paths=["prompts/final-reply"],
        package=__package__,
        model_family=model_family,
    )

    # Format the prompt
    final_reply_prompt = await kernel.prompts.format_prompt(
        final_reply_prompt,
        state=state,
    )

    # Add tools, some providers need this
    final_reply_prompt = final_reply_prompt.with_tools(
        *action_tools,
        *mcp_tools,
        *kernel.client_tools,
        *get_internal_tools(),
    )

    # And use the formatted prompt, model, and message to receive a stream
    # of output from the model as it processes the conversation
    async with platform.stream_response(final_reply_prompt, model) as stream:
        content_sink = message.sinks.content
        await stream.pipe_to(content_sink)

    # Commit the message to the thread and clear pending tool calls
    await message.commit()

    return state
