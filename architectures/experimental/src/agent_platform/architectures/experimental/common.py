from dataclasses import dataclass
from typing import Annotated, Protocol

from agent_platform.architectures.default.state import ArchState
from agent_platform.core import Kernel
from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass
class ToolToUse:
    """
    A tool to use with a reason and a double check that
    you actually have the tool and it is callable.
    """

    tool: Annotated[
        str,
        ("The name of the tool to use."),
    ]
    reason: Annotated[
        str,
        ("The reason you are using this tool."),
    ]
    index_of_callable_tool: Annotated[
        int,
        ("The index of the callable tool in the list of callable tools. "),
    ]
    problems: Annotated[
        str,
        (
            "Any issues, perhaps this tool is NOT a callable tool. "
            "Perhaps this is info you need to ask the user for."
        ),
    ]


@dataclass
class ToolsToUse:
    """
    A list of tools to use to make progress.
    These need to be CALLABLE tools!!
    """

    tools: Annotated[
        list[ToolToUse],
        (
            "The tools you need to use to make progress. "
            "You can't use a tool that you don't have. "
            "These need to be CALLABLE tools!!"
        ),
    ]


class StateWithMemories(Protocol):
    memories: list[str]


async def handle_max_iterations(kernel: Kernel, state: ArchState, max_iterations: int) -> ArchState:
    """
    System hook invoked when the agent reaches its autonomous-iteration cap.

    Emphasizes Runbook primacy and offers a single safe "Continue" quick option.
    """
    message = await kernel.thread_state.new_agent_message()
    message.append_content(
        f"I've reached my iteration limit. By default, I'm limited to {max_iterations} "
        "autonomous iterations before requiring human input.\n\n```sema4-json\n"
        '{ "type": "quick-options", "data": [{"message": "continue", '
        '"title": "Continue", "iconName": "IconContinueIcon"}]}\n```'
    )
    await message.stream_delta()
    await message.commit()

    return state


async def think(
    thought: Annotated[
        str,
        (
            "Optional, lightweight checkpoint used only when helpful for strict Runbook adherence. "
            "Typical triggers:\n"
            "• Multi-step Runbook needs a compact external checklist.\n"
            "• Ambiguity/branching about the next step or parameters.\n"
            "• Tool failure/unexpected output requires a short recovery plan.\n"
            "• About to begin a longer chain of calls (≈3--5+) and want a snapshot plan.\n"
            "• Truncation suspected; restate critical context/assumptions.\n"
            "Keep it terse: micro-checklist, next action, success criterion."
        ),
    ],
) -> dict[str, str]:
    """Reflection/coordination tool. Use sparingly.
    Most straightforward actions do not need `think`."""
    return {
        "result": "Thought recorded.",
    }


async def quick_reply(
    markdown: Annotated[
        str,
        ("A complete, brief, Markdown-formatted reply to the user's message."),
    ],
) -> dict[str, str]:
    """Terminal tool. Use only when the user's message can be fully satisfied by a brief response
    that does not require any other tools (including `consider_runbook_adherence`).
    Examples: greetings (“hi”), simple tests (“test”), capability questions (“what can you do?”).
    If you have used **any** non-terminal tool this turn, **do not** use `quick_reply`.
    `quick_reply` may not include charts or buttons; it renders plain markdown and returns
    control to the user. You MUST not call this tool in parallel, only one reply can be given."""
    return {"result": "Reply rendered."}


async def ready_to_reply_to_user(
    assessment: Annotated[
        str,
        (
            "One or two sentences proving readiness to reply **considering the Runbook**. "
            "Explicitly reference which Runbook steps are completed and "
            "the postconditions that were satisfied."
        ),
    ],
) -> dict[str, str]:
    """Terminal tool. Call only when the Runbook's completion criteria
    and all mapped steps have been met.
    Include a brief Runbook-referenced proof-of-completion in `assessment`."""
    return {
        "result": "Ready to reply.",
    }


async def unable_to_satisfy_request(
    reason: Annotated[
        str,
        (
            "One or two sentences explaining why you cannot proceed **with Runbook references** "
            "(e.g., missing step prerequisites, truncated Runbook, unavailable tool). "
            "Cite step IDs/names if applicable."
        ),
    ],
) -> dict[str, str]:
    """Terminal tool. Use only after exhausting reasonable Runbook-compliant options.
    Provide a concise, Runbook-referenced rationale in `reason`."""
    return {
        "result": "Unable to satisfy request.",
    }


async def consider_runbook_adherence(
    assessment: Annotated[
        str,
        (
            "A crisp check that you are following the Runbook exactly. "
            "State which Runbook steps are complete, "
            "which are in progress, and the next step.\n"
        ),
    ],
    next_steps: Annotated[
        str | None,
        (
            "A brief summary of the next steps you will take to make progress "
            "towards the user's request. This is optional, but if you feel the need "
            "to plan out your next steps, you can do so here. "
        ),
    ] = None,
    next_tools_to_use: Annotated[
        ToolsToUse | None,
        ("A list of tools to use to make progress. These need to be CALLABLE tools!!"),
    ] = None,
) -> dict[str, str]:
    """Primary discipline tool for documenting adherence
    and keeping progress aligned to the Runbook. If you are
    about to do something of consequence, and not 100% certain, use
    this tool to reflect on what the Runbook says. NEVER call this
    tool consecutively without making progress towards the user's via
    other tools."""
    if isinstance(next_tools_to_use, dict):
        next_tools_to_use = ToolsToUse(
            tools=[
                ToolToUse(
                    tool=tool["tool"],
                    reason=tool["reason"],
                    index_of_callable_tool=tool["index_of_callable_tool"],
                    problems=tool["problems"],
                )
                for tool in next_tools_to_use.get("tools", [])
            ],
        )

    notes = []
    if next_tools_to_use:
        for tool in next_tools_to_use.tools:
            if tool.problems:
                notes.append(f"Important: {tool.problems}")
            if tool.index_of_callable_tool < 0:
                notes.append(f"Important: {tool.tool} is NOT a callable tool!")
    return {
        "result": (
            "Runbook adherence considered. "
            "Next, I should use other tools to make progress towards the user's request. "
        )
        + (f"Notes: {', '.join(notes)}" if notes else ""),
    }


def get_internal_tools(kernel: Kernel, state: StateWithMemories) -> list[ToolDefinition]:
    """
    Return the internal coordination and terminal tools.
    """
    agent_settings = kernel.agent.extra.get("agent_settings", {})
    memory_enabled = agent_settings.get("enable_memory", False)

    tools = []

    async def _remember(memory: Annotated[str, "The memory to remember."]) -> dict[str, str]:
        """Remember a short piece of text for the duration of your interaction with the user.

        Use this sparingly, whenever you need to remember something important for the duration
        of your interaction with a user: say, an ID, or a URL, or any other key piece of
        information. You have a rolling window of messages between you and the user, so most
        things you don't need to explicitly remember, but for information that, if missing,
        you'd need to ask the user again, use this tool.
        """
        state.memories.append(memory)
        return {
            "result": f"Memory remembered, I now have {len(state.memories)} saved memories.",
        }

    if memory_enabled:
        tools.append(ToolDefinition.from_callable(_remember))

    tools.append(ToolDefinition.from_callable(quick_reply))
    tools.append(ToolDefinition.from_callable(consider_runbook_adherence))
    tools.append(ToolDefinition.from_callable(ready_to_reply_to_user))
    tools.append(ToolDefinition.from_callable(unable_to_satisfy_request))

    return tools
