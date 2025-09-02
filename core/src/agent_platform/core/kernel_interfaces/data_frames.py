import typing
from abc import ABC, abstractmethod

if typing.TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class DataFramesInterface(ABC):
    """Interface for data frames."""

    @abstractmethod
    async def step_initialize(self) -> None:
        """Caches all data frames internally and builds internal data.
        MUST be called before each processing step for data frames and tools
        to be correctly cached."""

    @property
    @abstractmethod
    def data_frames_summary(self) -> str:
        """Get a summary of the data frames (should be already included
        in the data_frames_system_prompt)."""

    @property
    @abstractmethod
    def data_frames_system_prompt(self) -> str:
        """Get a prompt to be added to the system prompt for the data frames."""

    @abstractmethod
    def get_data_frame_tools(self) -> "tuple[ToolDefinition, ...]":
        """Get tools related to data frames."""
