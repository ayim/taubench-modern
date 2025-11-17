import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, get_args

from agent_platform.architectures.experimental.consistency.plan import (
    FeedbackLevel,
    MonitorFeedbackEntry,
    NoteEntry,
    PlanStatus,
    PlanStep,
    PlanStepInput,
)
from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


def render_plan_snapshot(
    summary: str, steps: Sequence[PlanStep], assumptions: str | None = None
) -> str:
    """Renders a human-readable snapshot of the plan for prompt embedding."""
    if not steps:
        return "No plan steps have been recorded yet."

    lines: list[str] = [f"Plan summary: {summary.strip()}"] if summary else []

    if assumptions:
        lines.append("Assumptions / open items:")
        lines.extend(
            f"  - {line.strip()}" for line in assumptions.strip().splitlines() if line.strip()
        )

    lines.append("Ordered steps:")
    for idx, step in enumerate(steps, 1):
        lines.append(f"{idx}. [{step.status.upper()}] {step.title} (id: {step.step_id})")
        lines.append(f"     Instruction: {step.description}")
        if step.success_criteria:
            lines.append(f"     Success criteria: {step.success_criteria}")
        if step.notes:
            latest_note = step.notes[-1]
            lines.append(
                f"     Latest note [{latest_note['level']} "
                f"@ {latest_note['timestamp']}]: {latest_note['note']}"
            )
    return "\n".join(lines)


class ConsistencyToolsManager:
    """
    Manages the state and logic for the agent's internal lifecycle tools.

    This class encapsulates the operations that modify the agent's plan and
    execution state. It is instantiated with the current state and message,
    providing a clear and testable interface for each tool's implementation.
    """

    def __init__(
        self, state: ConsistencyArchState, message: ThreadMessageWithThreadState | None = None
    ):
        self.state = state
        self.message = message

    async def _sync_metadata(self) -> None:
        """Lazily imports and calls the metadata sync function."""
        from agent_platform.architectures.experimental.consistency.state_utils import (
            sync_consistency_metadata,
        )

        if self.message:
            await sync_consistency_metadata(self.state, self.message)

    def _now(self) -> str:
        """Returns the current UTC time as an ISO 8601 string."""
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _normalize_feedback_level(self, level_str: str, default: FeedbackLevel) -> FeedbackLevel:
        """Validates and normalizes a user-provided feedback level string."""
        normalized = level_str.strip().lower()
        # get_args(FeedbackLevel) returns ('info', 'warning', 'critical')
        if normalized in get_args(FeedbackLevel):
            return normalized  # type: ignore
        logger.warning(
            "Invalid feedback level '%s' provided; defaulting to '%s'.",
            level_str,
            default,
        )
        return default

    def _find_step_by_id(self, step_id: str) -> PlanStep:
        """Finds a plan step by its ID, raising a ValueError if not found."""
        step = next((s for s in self.state.plan_steps if s.step_id == step_id), None)
        if step is None:
            raise ValueError(f"Plan step with ID '{step_id}' not found.")
        return step

    def _find_current_step(self) -> tuple[int, PlanStep]:
        """Finds the currently active plan step, raising an error if none is active."""
        if not self.state.current_plan_step_id:
            raise ValueError("No active plan step is currently being executed.")

        active_step_tuple = next(
            (
                (i, s)
                for i, s in enumerate(self.state.plan_steps)
                if s.step_id == self.state.current_plan_step_id
            ),
            None,
        )
        if active_step_tuple is None:
            raise ValueError(
                f"Active plan step '{self.state.current_plan_step_id}' not found in plan."
            )
        return active_step_tuple

    def _activate_next_pending_step(self, start_index: int, timestamp: str) -> None:
        """Finds the next 'pending' step and sets its status to 'in_progress'."""
        next_step = next(
            (step for step in self.state.plan_steps[start_index:] if step.status == "pending"),
            None,
        )
        if next_step:
            next_step.status = "in_progress"
            next_step.last_updated = timestamp

    def _update_plan_status_if_completed(self) -> None:
        """Checks if all steps are complete and updates the overall plan status."""
        if self.state.plan_status == "failed" or not self.state.plan_steps:
            return

        if all(step.status in {"completed", "skipped"} for step in self.state.plan_steps):
            self.state.plan_status = "completed"

    async def _resolve_current_step(
        self, new_status: PlanStatus, note: str, level: FeedbackLevel
    ) -> dict[str, str]:
        """Core logic to resolve the current step with a new status and note."""
        index, step = self._find_current_step()
        timestamp = self._now()

        step.status = new_status
        step.last_updated = timestamp
        cleaned_note = note.strip()
        if cleaned_note:
            step.notes.append(NoteEntry(timestamp=timestamp, note=cleaned_note, level=level))

        self.state.current_step_resolution = {
            "status": new_status,
            "note": cleaned_note,
            "level": level,
            "timestamp": timestamp,
            "step_id": step.step_id,
            "index": index,
        }

        if new_status == "completed":
            self._activate_next_pending_step(index + 1, timestamp)

        self._update_plan_status_if_completed()
        await self._sync_metadata()

        logger.info("Current plan step resolved: step_id=%s status=%s", step.step_id, new_status)
        return {"result": f"Current plan step '{step.step_id}' marked as {new_status}."}

    # --- Tool Implementations ---

    async def define_plan(
        self,
        summary: Annotated[str, "Concise overview of the plan."],
        assumptions: Annotated[str, "Assumptions or guardrails for the plan."],
        steps: Annotated[list[PlanStepInput], "Ordered list of concrete steps."],
    ) -> dict[str, str]:
        """Creates the execution plan. This tool can only be called once."""
        if self.state.plan_steps:
            raise ValueError("A plan has already been registered; replanning is not supported.")
        if not steps:
            raise ValueError("The plan must include at least one step.")

        seen_ids = set()
        for i, step_input in enumerate(steps):
            step_id = (
                step_input.step_id
                if isinstance(step_input, PlanStepInput)
                else step_input.get("step_id")
            )
            if not step_id or not isinstance(step_id, str):
                raise ValueError(f"Step at index {i} is missing a valid 'step_id'.")
            if step_id.lower() in seen_ids:
                raise ValueError(f"Duplicate step_id detected: {step_id}")
            seen_ids.add(step_id.lower())

        self.state.plan_summary = summary.strip()
        self.state.plan_assumptions = assumptions.strip()
        self.state.plan_steps = [
            PlanStep.from_input(s if isinstance(s, PlanStepInput) else PlanStepInput(**s))
            for s in steps
        ]
        self.state.plan_status = "active"
        self.state.monitor_feedback_latest = MonitorFeedbackEntry(  # Reset feedback on new plan
            timestamp=self._now(),
            message="",
            level="info",
            related_steps=[],
        )
        self.state.plan_failure_reason = ""
        self.state.plan_failure_level = ""
        self.state.rework_requested_for_step_id = None

        await self._sync_metadata()
        logger.info("define_plan executed with %d steps.", len(self.state.plan_steps))
        return {"result": f"Plan registered with {len(steps)} steps."}

    async def record_monitor_feedback(
        self,
        feedback: Annotated[str, "Actionable feedback for the tool loop."],
        level: Annotated[str, "Severity: 'info', 'warning', or 'critical'."] = "info",
        related_steps: Annotated[list[str] | None, "Optional related step_ids."] = None,
    ) -> dict[str, str]:
        """Surfaces feedback from the monitor to the main tool loop controller."""
        normalized_level = self._normalize_feedback_level(level, "info")
        entry: MonitorFeedbackEntry = {
            "timestamp": self._now(),
            "message": feedback.strip(),
            "level": normalized_level,
            "related_steps": related_steps or [],
        }
        self.state.monitor_feedback_latest = entry
        self.state.monitor_feedback_history.append(entry)
        self.state.monitor_feedback_pending.append(entry)
        await self._sync_metadata()
        logger.info("record_monitor_feedback executed (level=%s)", normalized_level)
        return {"result": "Monitor feedback recorded."}

    async def complete_current_step(
        self, note: Annotated[str, "Optional note on why the step is complete."] = ""
    ) -> dict[str, str]:
        """Marks the current plan step as completed."""
        return await self._resolve_current_step("completed", note, "info")

    async def block_current_step(
        self,
        reason: Annotated[str, "Why the current step cannot be completed."],
        severity: Annotated[str, "Severity: 'info', 'warning', or 'critical'."] = "critical",
    ) -> dict[str, str]:
        """Marks the current plan step as blocked."""
        level = self._normalize_feedback_level(severity, "critical")
        return await self._resolve_current_step("blocked", reason, level)

    async def declare_plan_failed(
        self,
        reason: Annotated[str, "Why the entire plan cannot be executed safely."],
        severity: Annotated[str, "Severity: 'info', 'warning', or 'critical'."] = "critical",
    ) -> dict[str, str]:
        """Declares that the overall plan is no longer executable."""
        level = self._normalize_feedback_level(severity, "critical")
        timestamp = self._now()

        self.state.plan_status = "failed"
        self.state.plan_failure_reason = reason.strip()
        self.state.plan_failure_level = level

        failure_entry: MonitorFeedbackEntry = {
            "timestamp": timestamp,
            "message": self.state.plan_failure_reason or "Plan declared failed without reason.",
            "level": level,
            "related_steps": [],
        }
        self.state.monitor_feedback_latest = failure_entry
        self.state.monitor_feedback_history.append(failure_entry)
        self.state.monitor_feedback_pending.append(failure_entry)

        await self._sync_metadata()
        logger.warning("Plan declared failed: level=%s, reason=%s", level, reason.strip())
        return {"result": "Plan marked as failed."}

    async def request_step_rework(
        self,
        step_id: Annotated[str, "The ID of the plan step that requires more work."],
        reason: Annotated[str, "Actionable explanation of why the step is incomplete."],
    ) -> dict[str, str]:
        """Forces the agent to revisit a previously completed or blocked step."""
        target_step = self._find_step_by_id(step_id)
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise ValueError("A non-empty reason is required to request rework.")

        timestamp = self._now()
        logger.warning("Rework requested for step '%s'. Reason: %s", step_id, cleaned_reason)

        target_step.status = "in_progress"
        target_step.last_updated = timestamp
        target_step.notes.append(
            NoteEntry(
                timestamp=timestamp, note=f"Rework requested: {cleaned_reason}", level="warning"
            )
        )
        self.state.rework_requested_for_step_id = step_id

        feedback_entry: MonitorFeedbackEntry = {
            "timestamp": timestamp,
            "message": f"REWORK REQUESTED: {cleaned_reason}",
            "level": "warning",
            "related_steps": [step_id],
        }
        self.state.monitor_feedback_latest = feedback_entry
        self.state.monitor_feedback_history.append(feedback_entry)
        self.state.monitor_feedback_pending.append(feedback_entry)

        await self._sync_metadata()
        return {"result": f"Rework requested for step '{step_id}'."}


def build_consistency_tools(
    state: ConsistencyArchState,
    message: ThreadMessageWithThreadState | None = None,
) -> list[ToolDefinition]:
    """
    Factory function to build all consistency tool definitions.

    Instantiates the ConsistencyToolsManager and creates ToolDefinition
    objects from its public, tool-facing methods.
    """
    manager = ConsistencyToolsManager(state, message)

    return [
        ToolDefinition.from_callable(manager.define_plan, name="define_plan"),
        ToolDefinition.from_callable(
            manager.record_monitor_feedback, name="record_monitor_feedback"
        ),
        ToolDefinition.from_callable(manager.complete_current_step, name="complete_current_step"),
        ToolDefinition.from_callable(manager.block_current_step, name="block_current_step"),
        ToolDefinition.from_callable(manager.declare_plan_failed, name="declare_plan_failed"),
        ToolDefinition.from_callable(manager.request_step_rework, name="request_step_rework"),
    ]
