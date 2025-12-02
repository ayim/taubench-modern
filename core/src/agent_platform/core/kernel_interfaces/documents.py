import typing
from abc import ABC, abstractmethod
from typing import Literal, Protocol

if typing.TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class DocumentArchState(Protocol):
    """Protocol for the architecture state required for documents."""

    # Note: it's a string not a boolean so that we can easily add more states in the future.
    documents_tools_state: Literal["enabled", ""]


class DocumentsInterface(ABC):
    """Interface for documents."""

    @abstractmethod
    async def step_initialize(self, *, state: "DocumentArchState") -> None:
        """Caches all documents internally and builds internal data.
        MUST be called before each processing step for documents and tools
        to be correctly cached."""

    @abstractmethod
    async def is_enabled(self) -> bool:
        """Returns true if documents are enabled (and False otherwise)."""

    @abstractmethod
    def get_document_tools(self) -> "tuple[ToolDefinition, ...]":
        """Get tools related to documents."""
