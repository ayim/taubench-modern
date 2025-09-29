import typing
from typing import Annotated, Any

from structlog import get_logger

from agent_platform.core.kernel_interfaces.work_item import WorkItemArchState, WorkItemInterface
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.work_items import WorkItem
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin
from agent_platform.server.storage.option import StorageService

if typing.TYPE_CHECKING:
    from agent_platform.core.work_items import WorkItem
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class AgentServerWorkItemInterface(WorkItemInterface, UsesKernelMixin):
    """Handles interaction with the thread's work item."""

    def __init__(self):
        super().__init__()
        self._work_item: WorkItem | None = None
        self._work_item_tools: tuple[ToolDefinition, ...] = ()

    def is_enabled(self) -> bool:
        """Returns True if work items are enabled."""
        return True  # Always enabled for now

    async def step_initialize(self, state: WorkItemArchState) -> None:
        """Initialize work item for the current step."""
        storage = StorageService.get_instance()

        try:
            # Get the current work item from the thread
            if self.kernel.thread.work_item_id:
                self._work_item = await storage.get_work_item(self.kernel.thread.work_item_id)
            else:
                self._work_item = None
        except Exception:
            logger.exception("Error getting work item")
            self._work_item = None

        work_item_tools = WorkItemTools(
            self.kernel.user, self.kernel.thread.thread_id, self._work_item, storage
        )

        if self._work_item:
            # Only create tools if there's a work item
            self._work_item_tools = (
                ToolDefinition.from_callable(
                    work_item_tools.work_item_rename,
                    name="work_item_rename",
                ),
            )
            # Update state to indicate work item tools are enabled
            state.work_item_tools_state = "enabled"
        else:
            # No work item, no tools
            self._work_item_tools = ()
            state.work_item_tools_state = ""

    @property
    def work_item_summary_with_tools(self) -> str:
        if not self._work_item:
            return ""
        summary = f"## Work Item Summary:\n{self._current_work_item_summary}\n\n"
        # Add available tools information
        summary += "### Available Work Item Tools\n"
        summary += "• **work_item_rename**: You can rename the current work item"
        " using this tool when the user specifically requests a rename of the work item"
        " or the Runbook includes a step to rename the work item.\n"
        return summary

    @property
    def work_item_summary_no_tools(self) -> str:
        if not self._work_item:
            return ""
        summary = (
            "## Current Work Item Information\n"
            "A work item may have been available and/or managed in the prior conversation."
            " You must not use any tools this turn, but should you need to reference the"
            " current work item to discuss it or to better contextualize your response,"
            " you will find it here:\n\n"
        )
        summary += self._current_work_item_summary
        return summary

    @property
    def _current_work_item_summary(self) -> str:
        if not self._work_item:
            return ""

        summary = f"Current work item name: {self._work_item.work_item_name or 'Unnamed'}"
        # TODO: add other work item fields here
        return summary

    def get_work_item_tools(self) -> tuple[ToolDefinition, ...]:
        return self._work_item_tools


class WorkItemTools:
    """Tools for interacting with a thread's work item."""

    def __init__(
        self,
        user: "AuthedUser",
        tid: str,
        work_item: "WorkItem | None",
        storage: "BaseStorage",
    ):
        self._user = user
        self._tid = tid
        self._work_item = work_item
        self._storage = storage

    async def work_item_rename(
        self,
        new_work_item_name: Annotated[str, "The new name for the work item."],
    ) -> dict[str, Any]:
        """Rename the current work item."""
        if not self._work_item:
            return {
                "error_code": "no_work_item",
                "error": "No work item associated with this thread",
            }

        new_work_item_name = WorkItem.normalize_work_item_name(new_work_item_name) or ""

        if not new_work_item_name:
            return {
                "error_code": "empty_work_item_name",
                "error": "Work item name cannot be empty",
            }

        try:
            # Update the work item name
            self._work_item.work_item_name = new_work_item_name
            await self._storage.update_work_item(self._work_item)

            return {"result": f"Work item renamed to '{new_work_item_name}'"}
        except Exception as e:
            logger.exception(
                f"Error renaming work item {self._work_item.work_item_id} to {new_work_item_name}"
            )
            return {
                "error_code": "rename_failed",
                "error": f"Failed to rename work item: {e!r}",
            }
