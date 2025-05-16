"""
Default architecture for running agents.
"""

__author__ = "Sema4.ai Engineering"
__copyright__ = "Copyright 2025, Sema4.ai"
__license__ = "Proprietary"
__summary__ = "Default architecture for the Agent Platform"
__version__ = "0.0.1"
import logging

from agent_platform.architectures.default.state import ArchState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.prompts import select_prompt

logger = logging.getLogger(__name__)


@aa.entrypoint
async def entrypoint(kernel: Kernel, state: ArchState) -> ArchState:
    while True:
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
            raise ValueError(f"Unknown step: {state.step}")

    return state


@aa.step
async def _process_conversation_step(kernel: Kernel, state: ArchState) -> ArchState:
    # First, let's attempt to get any relevant tools from
    # our action packages and MCP servers
    action_tools, action_issues = await kernel.tools.from_action_packages(
        kernel.agent.action_packages,
        additional_headers={
            "x-invoked_by_assistant_id": kernel.agent.agent_id,
            "x-invoked_on_behalf_of_user_id": kernel.user.user_id,
            "x-invoked_for_thread_id": kernel.thread.thread_id,
        },
    )
    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(
        kernel.agent.mcp_servers,
    )
    # Save any issues to state for introspection
    state.configuration_issues = [*action_issues, *mcp_issues]

    # Get a platform and it's default LLM
    platform, model = await kernel.get_platform_and_model(model_type="llm")

    # Get the family of the chosen model
    model_family = platform.client.model_map.model_families[model]

    # Select and load the prompt we'll be using
    unformatted_conversation_prompt = select_prompt(
        prompt_paths=["prompts"],
        package=__package__,
        model_family=model_family,
    )

    # Format the prompt
    conversation_prompt = await kernel.prompts.format_prompt(
        unformatted_conversation_prompt,
        state=state,
    )

    # And let's add the tools to the prompt
    conversation_prompt = conversation_prompt.with_tools(*action_tools, *mcp_tools)

    # Let's create a new message in the thread
    message = await kernel.thread_state.new_agent_message()

    # And use the formatted prompt, model, and message to receive a stream
    # of output from the model as it processes the conversation
    async with platform.stream_response(conversation_prompt, model) as stream:
        await stream.pipe_to(
            # Sink thoughts / content / tool calls to message
            message.sinks.thoughts,
            message.sinks.content,
            message.sinks.tool_calls,
            # Sink pending tool calls and step
            # to state (so we can execute tools later)
            state.sinks.pending_tool_calls,
            state.sinks.step,
        )

    # Update the message to show that the tool calls are running in the chat
    for _, tool_call in state.pending_tool_calls:
        message.update_tool_running(tool_call.tool_call_id)
        await message.stream_delta()

    # Execute any pending tool calls and update the message
    async for _ in kernel.tools.execute_pending_tool_calls(
        state.pending_tool_calls,
        message,
    ):
        state.called_tools = True

    # Commit the message to the thread and clear pending tool calls
    await message.commit()

    return state
