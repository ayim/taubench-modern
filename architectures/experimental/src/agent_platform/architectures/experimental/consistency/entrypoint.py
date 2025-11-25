import logging
from enum import Enum, auto
from typing import Annotated

from agent_platform.architectures.experimental.consistency.executor import PlanExecutor
from agent_platform.architectures.experimental.consistency.internal_tools import (
    build_consistency_tools,
)
from agent_platform.architectures.experimental.consistency.prompts import build_prompt
from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.architectures.experimental.consistency.state_utils import (
    StateSync,
    push_plan_execution_phase,
    set_plan_execution_phase_fields,
)
from agent_platform.architectures.experimental.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa
from agent_platform.core.agent_architectures.special_commands import (
    handle_special_command,
    parse_special_command,
)
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


class TriageOutcome(Enum):
    """Represents the possible outcomes of the initial request triage."""

    QUICK_REPLY_ISSUED = auto()
    PROCEED_TO_PLANNING = auto()


class RequestTriage:
    """Encapsulates the logic for triaging a user request to determine the execution path."""

    def __init__(
        self,
        kernel: Kernel,
        platform: PlatformInterface,
        model: str,
        state: ConsistencyArchState,
        message: ThreadMessageWithThreadState,
    ):
        self.kernel = kernel
        self.platform = platform
        self.model = model
        self.state = state
        self.message = message

    async def _quick_reply(
        self, markdown: Annotated[str, "Markdown reply to send immediately."]
    ) -> dict[str, str]:
        """Terminal tool: Immediately reply to the user with simple markdown text."""
        return {"result": "Quick reply was rendered."}

    async def _proceed_with_planning(
        self, reason: Annotated[str, "Rationale for planning."]
    ) -> dict[str, str]:
        """Signal that the full planning and execution cycle is required."""
        logger.info("Triage decision: Proceeding to planning. Reason: %s", reason)
        return {"result": "Proceeding to main execution flow."}

    async def run(self) -> TriageOutcome:
        """Performs a lightweight triage to detect simple requests that can skip planning."""
        logger.info("Performing triage on user request.")
        self.state.pending_tool_calls.clear()

        triage_tools = [
            ToolDefinition.from_callable(self._quick_reply, name="quick_reply"),
            ToolDefinition.from_callable(self._proceed_with_planning),
        ]

        prompt = await build_prompt(
            self.kernel, state=self.state, prompt_path="prompts/triage-request", tools=triage_tools
        )

        async with self.platform.stream_response(prompt, self.model) as stream:
            await stream.pipe_to(
                self.message.sinks.reasoning,
                self.message.sinks.tool_calls(
                    forward_to_content="quick_reply", content_from_key="markdown"
                ),
                self.message.sinks.usage,
                self.state.sinks.pending_tool_calls,
            )

        if not self.state.pending_tool_calls:
            logger.warning("Triage produced no tool calls; defaulting to full planning.")
            return TriageOutcome.PROCEED_TO_PLANNING

        quick_reply_invoked = any(
            tool.name == "quick_reply" for tool, _ in self.state.pending_tool_calls
        )

        # Execute whichever tool the model chose.
        async for _ in self.kernel.tools.execute_pending_tool_calls(
            self.state.pending_tool_calls, self.message
        ):
            pass
        self.state.pending_tool_calls.clear()

        if quick_reply_invoked:
            logger.info("Triage outcome: Quick reply issued.")
            return TriageOutcome.QUICK_REPLY_ISSUED

        return TriageOutcome.PROCEED_TO_PLANNING


async def entrypoint_consistency(
    kernel: Kernel, state: ConsistencyArchState
) -> ConsistencyArchState:
    """Top-level entrypoint that initializes state and runs the processing pipeline."""
    try:
        logger.info("Consistency architecture starting turn.")
        if await _handle_special_command_if_present(kernel, state):
            return state

        return await _process_conversation_step(kernel, state)
    except Exception:
        logger.error(
            "Consistency architecture turn failed with an unhandled exception.", exc_info=True
        )
        raise
    finally:
        logger.info("Consistency architecture turn completed.")


async def _handle_special_command_if_present(kernel: Kernel, state: ConsistencyArchState) -> bool:
    """Checks for and handles special commands (e.g., /reset), returning True if handled."""
    try:
        latest_user_text = kernel.thread.latest_user_message_as_text
    except Exception:
        return False  # No user message to parse.

    cmd = parse_special_command(latest_user_text)
    if not cmd:
        return False

    logger.info("Special command detected: '%s'; bypassing normal loop.", cmd)
    was_handled = await handle_special_command(
        cmd,
        kernel,
        state=state,  # type: ignore[arg-type]
        internal_tools_provider=lambda: build_consistency_tools(state),
    )
    if was_handled:
        state.step = "done"
    return was_handled


@aa.step
async def _process_conversation_step(
    kernel: Kernel, state: ConsistencyArchState
) -> ConsistencyArchState:
    """Orchestrates the main agent workflow for a single conversation step."""
    from functools import partial

    kernel.converters.set_thread_message_conversion_function(
        partial(thread_messages_to_prompt_messages, state=state)
    )

    platform, model = await _resolve_platform_and_model(kernel, state)
    message = await kernel.thread_state.new_agent_message()
    await push_plan_execution_phase(
        state,
        message,
        phase="triage",
        caption="Thinking about whether we need a plan...",
    )

    # Step 1: Triage the user request to see if we can answer it immediately.
    triage = RequestTriage(kernel, platform, model, state, message)
    outcome = await triage.run()

    if outcome == TriageOutcome.QUICK_REPLY_ISSUED:
        async with StateSync(state, message):
            set_plan_execution_phase_fields(
                state,
                phase="done",
                caption="Replying without planning.",
            )
            state.step = "done"
        await message.commit()
        return state

    # Step 2: Proceed with the full planning and execution loop.
    state.consistency_tools = build_consistency_tools(state, message)
    executor = PlanExecutor(kernel, platform, model, state, message)
    await executor.run()

    # Step 3: Finalize and commit the results.
    async with StateSync(state, message):
        set_plan_execution_phase_fields(
            state,
            phase="done",
            caption="Turn complete.",
        )
        state.step = "done"
    await message.commit()
    return state


async def _resolve_platform_and_model(
    kernel: Kernel, state: ConsistencyArchState
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
