import typing
from abc import ABC, abstractmethod
from typing import Literal, Protocol

if typing.TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class WorkItemArchState(Protocol):
    """Protocol for the architecture state required for interacting with a work item."""

    work_item_tools_state: Literal["enabled", ""]


class WorkItemInterface(ABC):
    """Interface for the thread's optional work item."""

    @abstractmethod
    async def step_initialize(self, state: WorkItemArchState) -> None:
        """Initialize work item for the current step."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns true if work items are enabled."""

    @property
    @abstractmethod
    def work_item_summary_with_tools(self) -> str:
        """Get a summary of the work item with descriptions of the available tools."""

    @abstractmethod
    def work_item_summary_no_tools(self) -> str:
        """Get a summary of the work item without descriptions of the available tools."""

    @abstractmethod
    def get_work_item_tools(self) -> "tuple[ToolDefinition, ...]":
        """Get tools related to the thread's work item."""
