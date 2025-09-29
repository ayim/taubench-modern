from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core import agent_architectures as aa


@dataclass
class ArchState(aa.StateBase):
    class Sinks(aa.StateBase.Sinks):
        @property
        def step(self):
            """
            A sink to write the current step to the state when
            <step>step</step> occurs in stream.
            """
            return self.xml_tag_sink(
                field_name="step",
            )

    @property
    def sinks(self):
        """
        The sinks for the state.
        """
        return self.Sinks(self)

    users_name: str | None = field(
        default=None,
        metadata=aa.fields.user_scoped(
            description="The name of the user.",
        ),
    )
    """The name of the user we are interacting with (if known)."""

    configuration_issues: list[str] = field(
        default_factory=list,
    )
    """The configuration issues for the agent.

    We may fail to convert actions to tools, or fail to enumerate
    tools on MCP servers, or a whole host of other issues. This
    listing is intended to allow the agent to introspect on these
    issues and communicate them to the user, if necessary."""

    current_iteration: int = field(
        default=0,
    )
    """The current iteration of the agent.

    This is used to track the agent's progress and to determine
    if we need to stop execution."""

    agent_last_response_text: str = field(
        default="",
    )
    """The last response from the agent."""

    agent_last_response_tools_str: str = field(
        default="",
    )
    """The tools used in the last response from the agent."""

    processing_start_time: str = field(
        default="unknown",
    )
    """The time the agent started processing the user's request."""

    processing_elapsed_time: str = field(
        default="unknown",
    )
    """The elapsed time since the agent started processing the user's request."""

    state_parse_failure_count: int = field(
        default=0,
    )
    """The number of times we have failed to parse the state from the output format."""

    last_step_issues: list[str] = field(
        default_factory=list,
    )
    """The issues for the last step of the agent.

    This can hold a variety of issues, including but not limited
    to failure to parse the step from the output format."""

    called_tools: bool = field(
        default=False,
    )
    """Whether the agent has called any tools in the current step."""

    step: Literal[
        "initial",
        "processing",
        "done",
    ] = field(
        default="initial",
    )
    """The current step of the agent.

    This is used to track the agent's progress and to determine
    when the agent has finished processing the user's request."""

    # Note: it's a string not a boolean so that we can easily add more states in the future.
    data_frames_tools_state: Literal["enabled", ""] = field(
        default="",
    )
    """The state of the data frames tools. Note that after enabled we cannot go back to
    disabling it (tools cannot be removed from the context)"""

    work_item_tools_state: Literal["enabled", ""] = field(
        default="",
    )
    """The state of the work item tools. Note that after enabled we cannot go back to
    disabling it (tools cannot be removed from the context)"""
