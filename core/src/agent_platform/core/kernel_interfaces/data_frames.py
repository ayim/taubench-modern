from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from typing import Any, Literal, Protocol

if typing.TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.storage.base import BaseStorage


class DataFrameArchState(Protocol):
    """Protocol for the architecture state required for data frames."""

    # Note: it's a string not a boolean so that we can easily add more states in the future.
    data_frames_tools_state: Literal["enabled", ""]

    # Maps an unresolved file reference (from a semantic data model) to the matching info.
    empty_file_cache_key_to_matching_info: dict[str, dict]


class DataFramesInterface(ABC):
    """Interface for data frames."""

    @abstractmethod
    async def step_initialize(self, *, storage: BaseStorage | None = None, state: DataFrameArchState) -> None:
        """Caches all data frames internally and builds internal data.
        MUST be called before each processing step for data frames and tools
        to be correctly cached."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns true if data frames are enabled (and False otherwise
        )."""

    @property
    @abstractmethod
    def data_frames_summary(self) -> str:
        """Get a summary of the data frames (should be already included
        in the data_frames_system_prompt)."""

    @property
    @abstractmethod
    def data_frames_system_prompt(self) -> str:
        """Get a prompt to be added to the system prompt for the data frames."""

    @property
    @abstractmethod
    def data_frames_system_prompt_no_tools(self) -> str:
        """Get a prompt to be added to the system prompt for the data frames
        when no tools should be used."""

    @abstractmethod
    def get_data_frame_tools(self) -> tuple[ToolDefinition, ...]:
        """Get tools related to data frames."""

    @abstractmethod
    async def auto_create_data_frame(self, tool_def: ToolDefinition, result_output: Any) -> Any:
        """Auto create a data frame from the result output.

        Args:
            tool_def: The tool definition that created the result output.
            result_output: The result output from the tool.

        Returns:
            The new result that the LLM will see.
        """

    @abstractmethod
    async def on_upload_file_build_prompt(
        self, file_details: UploadedFile, is_work_item_attachment: bool = False
    ) -> str | None:
        """Build a prompt for the user after uploading a file.

        Args:
            file_details: The details of the uploaded file.
            is_work_item_attachment: Whether the uploaded file is a work item attachment.

        Returns:
            The prompt for the user after uploading a file, or None if no custom
            prompt should be added.
        """

    @abstractmethod
    def debug_data_frames_payload(self) -> list[dict[str, Any]]:
        """Return structured data frame information for diagnostics."""

    @abstractmethod
    def debug_semantic_data_models_payload(self) -> list[dict[str, Any]]:
        """Return structured semantic data model information for diagnostics."""
