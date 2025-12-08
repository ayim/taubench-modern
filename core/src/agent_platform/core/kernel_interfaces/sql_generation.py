from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin

if TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class SQLGenerationInterface(ABC, UsesKernelMixin):
    """Interface for SQL generation."""

    @abstractmethod
    async def step_initialize(self) -> None:
        """Initializes the SQL generation interface for the current step by caching
        semantic data models and building internal data.
        MUST be called before each processing step for SQL generation
        to be correctly cached."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns true if SQL generation is enabled (and False otherwise).

        Defaults to False as it should only be enabled within the SQL Generation Subagent.
        """

    @property
    @abstractmethod
    def sql_generation_system_prompt(self) -> str:
        """Get a prompt to be added to the system prompt for the SQL generation agent."""

    @abstractmethod
    def get_sql_generation_tools(self) -> tuple[ToolDefinition, ...]:
        """Get tools related to SQL generation."""
