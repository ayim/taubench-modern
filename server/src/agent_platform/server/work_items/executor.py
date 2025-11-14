from typing import Protocol

from agent_platform.core.work_items import WorkItem


class WorkItemExecutor(Protocol):
    """Protocol for work item execution callables."""

    async def __call__(self, item: WorkItem) -> bool:
        """
        Execute a single work item, runs the Judge (if necessary), and invokes any callbacks.
        This method updates the status in the database as execution progresses. If an exception
        is caught during execution, the work item state will be automatically updated in the
        database and this function will return False.

        If an Exception is raised by this function, the caller should attempt to transition
        the work item from EXECUTING to ERROR state to avoid orphaning the work item.

        Args:
            item: The work item to execute

        Returns:
            True if execution of the work item completely normally, False otherwise.
        """
        ...
