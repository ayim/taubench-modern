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
