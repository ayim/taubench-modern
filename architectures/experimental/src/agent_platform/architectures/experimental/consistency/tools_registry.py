import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.core import Kernel
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.tools.tool_definition import ToolDefinition

_EXCLUDED_FROM_PROMPT: Final[set[str]] = {"stage_for_final_reply"}


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

    def __init__(self, kernel: Kernel, state: ConsistencyArchState) -> None:
        self.kernel = kernel
        self.state = state

    async def _init_and_get_df_tools(self) -> Sequence[ToolDefinition]:
        await self.kernel.data_frames.step_initialize(state=self.state)
        return self.kernel.data_frames.get_data_frame_tools()

    async def _init_and_get_wi_tools(self) -> Sequence[ToolDefinition]:
        await self.kernel.work_item.step_initialize(state=self.state)
        return self.kernel.work_item.get_work_item_tools()

    async def _init_and_get_doc_tools(self) -> Sequence[ToolDefinition]:
        await self.kernel.documents.step_initialize(state=self.state)
        return self.kernel.documents.get_document_tools()

    async def _get_action_tools(
        self, *, refresh: bool
    ) -> tuple[Sequence[ToolDefinition], list[str]]:
        if refresh or not self.state.action_tools:
            tools, issues = await self.kernel.tools.from_action_packages(
                self.kernel.agent.action_packages
            )
            self.state.action_tools = tools
            self.state.action_issues = issues
        return self.state.action_tools, self.state.action_issues

    async def _get_mcp_tools(self, *, refresh: bool) -> tuple[Sequence[ToolDefinition], list[str]]:
        if refresh or not self.state.mcp_tools:
            tools, issues = await self.kernel.tools.from_mcp_servers(self.kernel.agent.mcp_servers)
            self.state.mcp_tools = tools
            self.state.mcp_issues = issues
        return self.state.mcp_tools, self.state.mcp_issues

    async def gather(
        self,
        message: ThreadMessageWithThreadState,
        *,
        refresh: bool = False,
    ) -> tuple[ToolsBundle, list[str]]:
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
        df_task = asyncio.create_task(self._init_and_get_df_tools())
        wi_task = asyncio.create_task(self._init_and_get_wi_tools())
        doc_task = asyncio.create_task(self._init_and_get_doc_tools())
        action_task = asyncio.create_task(self._get_action_tools(refresh=refresh))
        mcp_task = asyncio.create_task(self._get_mcp_tools(refresh=refresh))

        # Await all results in one go.
        (
            df_tools,
            wi_tools,
            doc_tools,
            (action_tools, action_issues),
            (mcp_tools, mcp_issues),
        ) = await asyncio.gather(df_task, wi_task, doc_task, action_task, mcp_task)

        bundle = ToolsBundle(
            action=action_tools,
            mcp=mcp_tools,
            client=self.kernel.client_tools,
            dataframes=df_tools,
            work_items=wi_tools,
            documents=doc_tools,
        )

        combined_tools = (*bundle.as_tuple(), *self.state.consistency_tools)
        message.update_tools_metadata(combined_tools)

        issues: list[str] = [*action_issues, *mcp_issues]
        return bundle, issues

    @staticmethod
    def format_for_prompt(tools: ToolsBundle) -> str:
        """
        Produce a concise, markdown-friendly list of available tools
        for inclusion in a plan prompt.

        Filters out any tools in `_EXCLUDED_FROM_PROMPT`.
        """
        all_tools = tools.as_tuple()
        if not all_tools:
            return "No tools are available for execution."

        visible = (t for t in all_tools if t.name not in _EXCLUDED_FROM_PROMPT)
        lines = ["Here are the tools you can use in the plan's steps:"]
        for tool in sorted(visible, key=lambda t: t.name):
            lines.append(f"- **`{tool.name}`**: {tool.description}")
        return "\n".join(lines)
