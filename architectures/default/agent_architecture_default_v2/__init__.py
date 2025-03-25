from agent_architecture_default_v2.state import ArchState
from agent_server_types_v2 import Kernel
from agent_server_types_v2 import agent_architectures as aa


@aa.entrypoint
async def entrypoint(kernel: Kernel, state: ArchState) -> ArchState:
    while True:
        if state.step in ("processing", "initial"):
            state = await _process_conversation_step(kernel, state)
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
    )
    mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(
        kernel.agent.mcp_servers,
    )
    # Save any issues to state for introspection
    state.configuration_issues = [*action_issues, *mcp_issues]

    # Load and format the prompt we'll be using
    conversation_prompt = await kernel.prompts.load_and_format(
        "prompts/conversation-default.yml",
        state,
    )

    # And let's add the tools to the prompt
    conversation_prompt = conversation_prompt.with_tools(*action_tools, *mcp_tools)

    # Let's create a new message in the thread
    message = await kernel.thread_state.new_agent_message()

    # Get a platform and it's default LLM
    platform, model = await kernel.get_platform_and_model(model_type="llm")

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

    # Execute any pending tool calls and update the message
    async for result in kernel.tools.execute_pending_tool_calls(
        state.pending_tool_calls,
    ):
        message.update_tool_result(result)
        await message.stream_delta()
        state.called_tools = True

    # Commit the message to the thread and clear pending tool calls
    await message.commit()

    return state
