from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from agent_platform.architectures.experimental.violet.docintel.types import DocIntState
from agent_platform.core import agent_architectures as aa
from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
from agent_platform.core.kernel_interfaces.documents import DocumentArchState
from agent_platform.core.kernel_interfaces.work_item import WorkItemArchState


@dataclass(slots=True)
class VioletState(aa.StateBase, DataFrameArchState, WorkItemArchState, DocumentArchState):
    """State for the Violet architecture."""

    # -- Core Execution & Timing State -------------------------------------------
    step: Literal[
        "initial",
        "processing",
        "gathering-pdf-context",
        "done",
    ] = field(default="initial")
    """The overall lifecycle phase of the agent turn."""

    current_iteration: int = field(default=0)
    """The current iteration of the agent's main loop."""

    processing_start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
    """Timestamp (ISO 8601) when the current processing turn began."""

    processing_elapsed_time: str = "0.00 seconds"
    """A human-readable string representing the time elapsed since processing started."""

    ignored_reasoning_ids: list[str] = field(default_factory=list)
    """The IDs of the reasoning that have been ignored during the current processing turn.

    Ignored reasoning happens when we use separate out-of-band prompts before/during the main
    agent loop to accomplish certain tasks (e.g., schema inference). We don't want to slice
    this reasoning back into the context during the main agent loop, so we ignore it."""

    # -- Kernel Interface State ---------------------------------------------------
    documents_tools_state: Literal["enabled", ""] = field(default="")
    """The state of the documents tools."""

    work_item_tools_state: Literal["enabled", ""] = field(default="")
    """The state of the work item tools."""

    data_frames_tools_state: Literal["enabled", ""] = field(default="")
    """The state of the data frames tools."""

    empty_file_cache_key_to_matching_info: dict[str, dict] = field(default_factory=dict)
    """Maps an unresolved file reference (from a semantic data model) to the matching info."""

    # -- Model & Platform Configuration ------------------------------------------
    # These fields are used in our prompts to help contextualize the agent as to
    # what model it's being driven by.
    selected_platform: str = field(default="")
    """The name of the model platform being used (e.g., 'google-vertex-ai')."""

    selected_model_provider: str = field(default="")
    """The provider of the model (e.g., 'google')."""

    selected_model: str = field(default="")
    """The specific model name being used (e.g., 'gemini-3-pro-high')."""

    # -- Document Intelligence (Doc Cards + Markup) -----------------------------
    doc_int: DocIntState = field(default_factory=DocIntState)
    """Document intelligence state persisted on the thread."""

    # -- Sinks -------------------------------------------------------------------
    # The `sinks` property provides a controlled interface for other parts of the
    # architecture to write data back into this state object, typically during
    # the processing of a streaming model response.
    Sinks: ClassVar[Any]
    """A placeholder for the nested Sinks class, defined in the base class."""

    @property
    def sinks(self):
        """Provides access to sink methods for updating state from external sources."""
        return self.Sinks(self)
