from copy import deepcopy
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.mcp import MCPServer
from agent_platform.core.platforms import AnyPlatformParameters
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class Agent:
    """Agent definition."""

    name: str = field(metadata={"description": "The name of the agent."})
    """The name of the agent."""

    description: str = field(
        metadata={"description": "The description of the agent."},
    )
    """The description of the agent."""

    user_id: str = field(
        metadata={"description": "The id of the user that created the agent."},
    )
    """The id of the user that created the agent."""

    # TODO: Revert this to `runbook` maybe in the future? This field was
    # renamed throughout our code to allow using `runbook` (as a plain
    # string) for clients.
    runbook_structured: Runbook = field(
        metadata={"description": "The structured runbook of the agent."},
    )
    """The structured runbook of the agent."""

    version: str = field(metadata={"description": "The version of the agent."})
    """The version of the agent."""

    platform_configs: list[AnyPlatformParameters] = field(
        metadata={"description": "The platform configs this agent can use."},
    )
    """The platform configs this agent can use."""

    agent_architecture: AgentArchitecture = field(
        metadata={"description": "The architecture details for the agent."},
    )
    """The architecture details for the agent."""

    action_packages: list[ActionPackage] = field(
        metadata={"description": "The action packages this agent uses."},
        default_factory=list,
    )
    """The action packages this agent uses."""

    mcp_servers: list[MCPServer] = field(
        metadata={
            "description": "The Model Context Protocol (MCP) servers this agent uses.",
        },
        default_factory=list,
    )
    """The Model Context Protocol (MCP) servers this agent uses."""

    question_groups: list[QuestionGroup] = field(
        metadata={"description": "The question groups of the agent."},
        default_factory=list,
    )
    """The question groups of the agent."""

    observability_configs: list[ObservabilityConfig] = field(
        metadata={"description": "The observability configs of the agent."},
        default_factory=list,
    )
    """The observability configs of the agent."""

    created_at: datetime = field(
        metadata={"description": "The creation time of the agent."},
        default_factory=lambda: datetime.now(UTC),
    )
    """The creation time of the agent."""

    updated_at: datetime = field(
        metadata={"description": "The last update time of the agent."},
        default_factory=lambda: datetime.now(UTC),
    )
    """The last update time of the agent."""

    mode: Literal["conversational", "worker"] = field(
        metadata={"description": "The mode of the agent."},
        default="conversational",
    )
    """The mode of the agent."""

    agent_id: str = field(
        metadata={"description": "The unique identifier of the agent."},
        default_factory=lambda: str(uuid4()),
    )
    """The unique identifier of the agent."""

    extra: dict[str, Any] = field(
        metadata={"description": "Extra fields for the agent."},
        default_factory=dict,
    )
    """Extra fields for the agent."""

    def __post_init__(self) -> None:
        """Post-initialization checks."""
        assert_literal_value_valid(self, "mode")

    def copy(self, **updates: Any) -> "Agent":  # noqa: C901, PLR0912
        """
        Returns a deep copy of the agent, optionally applying updates.

        Args:
            **updates: Keyword arguments for fields to update in the copy.
                       Values provided in updates will overwrite the corresponding
                       fields from the original agent. Nested objects provided
                       in updates should be complete objects of the expected type.

        Returns:
            A new Agent instance with the applied updates.

        Raises:
            TypeError: If `updates` contains keys that are not fields of the Agent.
        """
        # Validate update keys first
        all_field_names = {f.name for f in fields(self)}
        for key in updates:
            if key not in all_field_names:
                raise TypeError(f"'{key}' is an invalid keyword argument for copy()")

        # Prepare arguments for the new Agent instance
        constructor_args = {}
        for field_info in fields(self):
            field_name = field_info.name

            if field_name in updates:
                constructor_args[field_name] = deepcopy(updates[field_name])
            else:
                original_value = getattr(self, field_name)

                if field_name == "runbook":
                    constructor_args[field_name] = original_value.copy()
                elif field_name == "action_packages":
                    constructor_args[field_name] = [pkg.copy() for pkg in original_value]
                elif field_name == "mcp_servers":
                    constructor_args[field_name] = [server.copy() for server in original_value]
                elif field_name == "agent_architecture":
                    constructor_args[field_name] = original_value.copy()
                elif field_name == "question_groups":
                    constructor_args[field_name] = [group.copy() for group in original_value]
                elif field_name == "platform_configs":
                    constructor_args[field_name] = [
                        config.model_copy() for config in original_value
                    ]
                elif field_name == "observability_configs":
                    constructor_args[field_name] = [config.copy() for config in original_value]
                elif field_name == "extra":
                    constructor_args[field_name] = deepcopy(original_value)
                else:
                    constructor_args[field_name] = deepcopy(original_value)

        new_agent = Agent(**constructor_args)
        return new_agent

    def model_dump(self) -> dict:
        """Serializes the agent to a dictionary. Useful for JSON serialization."""
        return {
            "action_packages": [
                action_package.model_dump() for action_package in self.action_packages
            ],
            "mcp_servers": [mcp_server.model_dump() for mcp_server in self.mcp_servers],
            "agent_architecture": self.agent_architecture.model_dump(),
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "extra": self.extra,
            "mode": self.mode,
            "platform_configs": [
                platform_config.model_dump() for platform_config in self.platform_configs
            ],
            "name": self.name,
            "observability_configs": [
                observability_config.model_dump()
                for observability_config in self.observability_configs
            ],
            "question_groups": [
                question_group.model_dump() for question_group in self.question_groups
            ],
            "runbook_structured": self.runbook_structured.model_dump(),
            "agent_id": self.agent_id,
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id,
            "version": self.version,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "Agent":
        """Create an agent from a dictionary."""
        # Create a copy to avoid modifying the input
        data = data.copy()

        # Handle UUIDs
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])

        # Parse nested objects
        actions_packages = [
            ActionPackage.model_validate(action_package)
            for action_package in data.pop("action_packages", [])
        ]
        mcp_servers = [
            MCPServer.model_validate(mcp_server) for mcp_server in data.pop("mcp_servers", [])
        ]
        agent_architecture = AgentArchitecture.model_validate(
            data.pop("agent_architecture", {}),
        )
        observability_configs = [
            ObservabilityConfig.model_validate(observability_config)
            for observability_config in data.pop("observability_configs", [])
        ]
        question_groups = [
            QuestionGroup.model_validate(question_group)
            for question_group in data.pop("question_groups", [])
        ]
        runbook_structured = Runbook.model_validate(data.pop("runbook_structured", {}))
        platform_configs = [
            PlatformParameters.model_validate(platform_config)
            for platform_config in data.pop("platform_configs", [])
        ]

        # Parse datetime fields
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(
            action_packages=actions_packages,
            mcp_servers=mcp_servers,
            agent_architecture=agent_architecture,
            observability_configs=observability_configs,
            question_groups=question_groups,
            runbook_structured=runbook_structured,
            platform_configs=cast(list[AnyPlatformParameters], platform_configs),
            **data,
        )
