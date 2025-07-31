from typing import Annotated

from agent_platform.architectures.default.state import ArchState
from agent_platform.core import Kernel
from agent_platform.core.tools.tool_definition import ToolDefinition


async def handle_max_iterations(kernel: Kernel, state: ArchState, max_iterations: int) -> ArchState:
    message = await kernel.thread_state.new_agent_message()
    message.append_content(
        f"I've reached my iteration limit. By default, I'm limited to {max_iterations} "
        "autonomous iterations before requiring human input.\n\n```sema4-json\n"
        '{ "type": "quick-options", "data": [{"message": "continue", '
        '"title": "Continue", "iconName": "IconContinueIcon" }]}\n```'
    )
    await message.stream_delta()
    await message.commit()

    return state


async def think(
    thought: Annotated[
        str,
        (
            "A reflection on the current state of the conversation and any progress "
            "made towards the user's goal, or any issues encountered."
        ),
    ],
) -> dict[str, str]:
    """A tool to think about the current state of the conversation, if you need to
    reflect, diagnose failing tools, get back on track, or just consider your next
    steps, use this tool."""

    return {
        "thought": thought,
    }


async def ready_to_reply_to_user(
    assessment: Annotated[
        str,
        ("A short sentence or two describing your plan for a user-facing reply."),
    ],
) -> dict[str, str]:
    """A tool to assess whether you're ready to reply to the user. If you're not,
    use the `think` tool to reflect and plan your next steps or use your other tools
    to gather data and make more progress. When you're ready to reply to the user,
    use this tool."""
    return {
        "ready_to_reply": "yes",
    }


async def unable_to_satisfy_request(
    reason: Annotated[
        str,
        ("A short sentence or two describing why you're unable to satisfy the request."),
    ],
) -> dict[str, str]:
    """A tool to indicate that you're unable to satisfy the request. This is a last
    resort tool to use when you've exhausted all other options."""
    return {
        "unable_to_satisfy_request": "yes",
        "error_code": "unable_to_satisfy_request",
        "message": "I'm unable to satisfy the request.",
    }


def get_internal_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition.from_callable(think),
        ToolDefinition.from_callable(ready_to_reply_to_user),
        ToolDefinition.from_callable(unable_to_satisfy_request),
    ]
