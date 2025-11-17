from datetime import UTC, datetime
from typing import Any

from agent_platform.architectures.experimental.consistency.plan import (
    FeedbackLevel,
    NoteEntry,
    PlanStep,
)


def blocked_resolution(
    step: PlanStep,
    step_index: int,
    note: str,
    level: FeedbackLevel = "warning",
) -> dict[str, Any]:
    """Updates a plan step to a 'blocked' state and returns a resolution dict.

    This function serves two purposes:
    1. It mutates the provided `step` object, setting its status and appending a
       note to its history.
    2. It creates and returns a dictionary payload that represents this resolution
       event, which is then stored in the agent's state.

    Args:
        step: The `PlanStep` object to modify.
        step_index: The index of the step within the plan.
        note: The reason why the step is blocked.
        level: The severity level of the block ('info', 'warning', or 'critical').

    Returns:
        A dictionary containing the details of the 'blocked' resolution event.

    Side Effects:
        - Modifies `step.status` to "blocked".
        - Modifies `step.last_updated` to the current UTC timestamp.
        - Appends a new note dictionary to `step.notes`.
    """
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")

    # --- Side Effect: Mutate the PlanStep object ---
    step.status = "blocked"
    step.last_updated = timestamp
    step.notes.append(NoteEntry(timestamp=timestamp, note=note, level=level))

    # --- Return Value: Create the resolution payload ---
    return {
        "status": "blocked",
        "note": note,
        "level": level,
        "timestamp": timestamp,
        "step_id": step.step_id,
        "index": step_index,
    }
