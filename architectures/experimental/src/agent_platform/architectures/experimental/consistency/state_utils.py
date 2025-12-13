import logging
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any, Final

from agent_platform.architectures.experimental.consistency.internal_tools import (
    render_plan_snapshot,
)
from agent_platform.architectures.experimental.consistency.plan import PlanExecutionPhase
from agent_platform.architectures.experimental.consistency.state import (
    ConsistencyArchState,
    MonitorFeedbackEntry,
)
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState

# --- Constants ---
MAX_MONITOR_HISTORY: Final[int] = 25
_METADATA_ROOT_KEY: Final[str] = "consistency"
_PLAN_KEY: Final[str] = "plan"
_MONITOR_KEY: Final[str] = "monitor"
_EXECUTION_KEY: Final[str] = "execution"

logger = logging.getLogger(__name__)


class StateSync(AbstractAsyncContextManager):
    """An async context manager to ensure state is synced upon exit.

    This is a convenience wrapper around `sync_consistency_metadata`. Any code
    that modifies the state within its `async with` block will trigger a sync
    to the message metadata when the block is exited, ensuring the UI-facing
    metadata is always up-to-date.
    """

    def __init__(self, state: ConsistencyArchState, message: ThreadMessageWithThreadState):
        self.state = state
        self.message = message

    async def __aenter__(self) -> "StateSync":
        """Enters the context, returning itself."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exits the context and triggers the metadata sync."""
        await sync_consistency_metadata(self.state, self.message)


def set_plan_execution_phase_fields(
    state: ConsistencyArchState,
    phase: PlanExecutionPhase,
    caption: str,
) -> None:
    """Updates execution phase fields without triggering a sync."""
    state.plan_execution_phase = phase
    state.plan_execution_caption = caption
    state.plan_execution_changed_at = datetime.now(UTC).isoformat(timespec="seconds")


async def push_plan_execution_phase(
    state: ConsistencyArchState,
    message: ThreadMessageWithThreadState,
    phase: PlanExecutionPhase,
    caption: str,
) -> None:
    """Updates the execution phase fields and immediately syncs metadata."""
    set_plan_execution_phase_fields(state, phase, caption)
    await sync_consistency_metadata(state, message)


async def sync_consistency_metadata(
    state: ConsistencyArchState,
    message: ThreadMessageWithThreadState,
) -> None:
    """Syncs the plan, monitor, and execution state to the message metadata.

    This function orchestrates the construction of several data payloads
    (plan, monitor, execution) from the current state and attaches them to the
    `message.agent_metadata` dictionary. It is the primary mechanism for
    exposing the agent's internal state to external observers like a UI.

    Side Effects:
        - Modifies `state.plan_snapshot` with a newly rendered string.
        - Trims `state.monitor_feedback_history` to `MAX_MONITOR_HISTORY`.
        - Modifies `message.agent_metadata` with the new payloads.
        - Calls `message.stream_delta()` to push metadata updates.
    """
    # 1. Update the plan snapshot string used in prompts.
    state.plan_snapshot = render_plan_snapshot(
        state.plan_summary,
        state.plan_steps,
        state.plan_assumptions,
    )

    # 2. Perform any direct state mutations, like trimming history.
    trimmed_history = state.monitor_feedback_history[-MAX_MONITOR_HISTORY:]
    state.monitor_feedback_history = trimmed_history

    # 3. Build the discrete metadata payloads.
    plan_payload = _build_plan_payload(state)
    monitor_payload = _build_monitor_payload(history=trimmed_history, latest=state.monitor_feedback_latest)
    execution_payload = _build_execution_payload(state)

    # 4. Attach payloads to the message metadata.
    metadata_root = message.agent_metadata.setdefault(_METADATA_ROOT_KEY, {})
    metadata_root[_PLAN_KEY] = plan_payload
    metadata_root[_MONITOR_KEY] = monitor_payload
    metadata_root[_EXECUTION_KEY] = execution_payload

    # 5. Stream the changes and log for debugging.
    await message.stream_delta()
    logger.debug(
        "Consistency metadata synced: steps=%d, plan_status=%s, monitor_latest=%s",
        len(state.plan_steps),
        state.plan_status,
        (state.monitor_feedback_latest or {}).get("level", "none"),
    )


def _build_plan_payload(state: ConsistencyArchState) -> dict[str, Any]:
    """Constructs the 'plan' dictionary for agent metadata."""
    payload = {
        "summary": state.plan_summary,
        "assumptions": state.plan_assumptions,
        "steps": [step.to_metadata() for step in state.plan_steps],
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": state.plan_status,
    }
    if state.plan_failure_reason:
        payload["failure"] = {
            "reason": state.plan_failure_reason,
            "level": state.plan_failure_level,
        }
    return payload


def _build_monitor_payload(history: list[MonitorFeedbackEntry], latest: MonitorFeedbackEntry) -> dict[str, Any]:
    """Constructs the 'monitor' dictionary for agent metadata."""
    return {"latest": latest, "history": history}


def _build_execution_payload(state: ConsistencyArchState) -> dict[str, Any]:
    """Constructs the 'execution' dictionary for agent metadata."""
    payload: dict[str, Any] = {
        "phase": state.plan_execution_phase,
        "caption": state.plan_execution_caption,
        "changed_at": state.plan_execution_changed_at,
        "active_step_id": state.current_plan_step_id,
        "active_step_index": state.current_plan_step_index,
    }

    # Find the active step object efficiently.
    active_step = (
        next(
            (s for s in state.plan_steps if s.step_id == state.current_plan_step_id),
            None,
        )
        if state.current_plan_step_id
        else None
    )

    if active_step:
        payload["active_step_title"] = active_step.title
        payload["active_step_status"] = active_step.status

    if state.last_step_resolution:
        payload["last_step_resolution"] = state.last_step_resolution

    return payload
