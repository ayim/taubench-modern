from typing import ClassVar

from agent_platform.core.work_items.work_item import WorkItemStatus


class WorkItemStateMachine:
    """State machine for managing WorkItem status transitions.

    Implements the following state transition rules:
    - PRECREATED -> PENDING, CANCELLED
    - DRAFT -> PENDING, CANCELLED
    - PENDING -> EXECUTING, CANCELLED
    - EXECUTING -> NEEDS_REVIEW, COMPLETED, ERROR, CANCELLED, INDETERMINATE
    - NEEDS_REVIEW -> COMPLETED, PENDING
    - INDETERMINATE -> PENDING, COMPLETED
    - COMPLETED -> PENDING
    - ERROR -> PENDING, COMPLETED
    - CANCELLED -> PENDING, COMPLETED
    """

    # Define allowed transitions from each state
    _TRANSITIONS: ClassVar[dict[WorkItemStatus, set[WorkItemStatus]]] = {
        WorkItemStatus.PRECREATED: {
            WorkItemStatus.PENDING,
            WorkItemStatus.CANCELLED,
        },
        WorkItemStatus.DRAFT: {
            WorkItemStatus.PENDING,
            WorkItemStatus.CANCELLED,
        },
        WorkItemStatus.PENDING: {
            WorkItemStatus.EXECUTING,
            WorkItemStatus.CANCELLED,
        },
        WorkItemStatus.EXECUTING: {
            # restart can move an EXECUTING to PENDING, but this is an exceptional case.
            WorkItemStatus.NEEDS_REVIEW,
            WorkItemStatus.COMPLETED,
            WorkItemStatus.ERROR,
            WorkItemStatus.CANCELLED,
            WorkItemStatus.INDETERMINATE,
        },
        WorkItemStatus.NEEDS_REVIEW: {  # /continue or /restart will move back to PENDING
            WorkItemStatus.COMPLETED,
            WorkItemStatus.PENDING,
        },
        WorkItemStatus.INDETERMINATE: {  # /continue or /restart will move back to PENDING
            WorkItemStatus.PENDING,
            WorkItemStatus.COMPLETED,
        },
        WorkItemStatus.COMPLETED: {  # /restart
            WorkItemStatus.PENDING,
        },
        WorkItemStatus.ERROR: {  # /restart will move back to PENDING
            WorkItemStatus.PENDING,
            WorkItemStatus.COMPLETED,
        },
        WorkItemStatus.CANCELLED: {  # /restart or /complete
            WorkItemStatus.PENDING,
            WorkItemStatus.COMPLETED,
        },
    }

    @classmethod
    def is_valid_transition(cls, from_status: WorkItemStatus, to_status: WorkItemStatus) -> bool:
        """Check if transitioning from one status to another is valid.

        Args:
            from_status: The current status
            to_status: The desired new status

        Returns:
            True if the transition is valid, False otherwise
        """
        return to_status in cls._TRANSITIONS.get(from_status, set())
