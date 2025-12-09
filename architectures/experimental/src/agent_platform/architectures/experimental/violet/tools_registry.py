import logging
from collections.abc import Sequence
from dataclasses import dataclass

from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core import Kernel
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolsBundle:
    """
    An immutable container for the different classes of tools that can be surfaced to the agent.
    Inputs are normalized to tuples so iteration and reuse are predictable.
    """

    action: Sequence[ToolDefinition]
    mcp: Sequence[ToolDefinition]
    client: Sequence[ToolDefinition]
    dataframes: Sequence[ToolDefinition]
    work_items: Sequence[ToolDefinition]
    documents: Sequence[ToolDefinition]

    def __post_init__(self) -> None:
        # Normalize to tuples for immutability and consistent downstream usage.
        self.action = tuple(self.action)
        self.mcp = tuple(self.mcp)
        self.client = tuple(self.client)
        self.dataframes = tuple(self.dataframes)
        self.work_items = tuple(self.work_items)
        self.documents = tuple(self.documents)

    def as_tuple(self) -> tuple[ToolDefinition, ...]:
        """Return all tools in a single flattened tuple."""
        return (
            *self.action,
            *self.mcp,
            *self.client,
            *self.dataframes,
            *self.work_items,
            *self.documents,
        )

    def __iter__(self):
        return iter(self.as_tuple())


class ToolsRegistry:
    """
    Resolves, caches, and formats tool definitions that are available to the agent.
    """

    def __init__(
        self, kernel: Kernel, state: VioletState, message: ThreadMessageWithThreadState
    ) -> None:
        self.kernel = kernel
        self.state = state
        self.message = message
        self._documents = None

    async def gather(
        self,
        message: ThreadMessageWithThreadState,
        *,
        refresh: bool = False,
    ) -> ToolsBundle:
        """
        Collect tools from all sources, optionally refreshing cached action/mcp tools.

        Runs the following concurrently:
          - dataframe init + tool retrieval
          - work-item init + tool retrieval
          - document init + tool retrieval
          - action tools (cached unless refresh=True)
          - MCP tools (cached unless refresh=True)

        Side effect: updates the tools metadata for the message.
        Returns: (bundle, issues)
        """
        # Kick off all work concurrently.
        await self.kernel.data_frames.step_initialize(state=self.state)
        data_frames_tools = self.kernel.data_frames.get_data_frame_tools()

        bundle = ToolsBundle(
            action=[],
            mcp=[],
            client=self.kernel.client_tools,
            dataframes=data_frames_tools,
            work_items=[],
            documents=await self._gather_document_tools(),
        )

        message.update_tools_metadata(bundle.as_tuple())

        return bundle

    async def _gather_document_tools(self) -> tuple[ToolDefinition, ...]:
        try:
            from agent_platform.architectures.experimental.violet.docintel.tools import (
                VioletDocumentsInterface,
            )

            if self._documents is None:
                self._documents = VioletDocumentsInterface(self.kernel, self.state, self.message)

            await self._documents.initialize()
            return self._documents.get_tools()
        except Exception:
            logger.exception("Failed to initialize Violet document tools")
            return ()
