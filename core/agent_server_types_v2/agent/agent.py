from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID, uuid4

from agent_server_types_v2.actions.action_package import ActionPackage
from agent_server_types_v2.agent.agent_architecture import AgentArchitecture
from agent_server_types_v2.agent.observability_config import ObservabilityConfig
from agent_server_types_v2.agent.question_group import QuestionGroup
from agent_server_types_v2.runbook.runbook import Runbook
from agent_server_types_v2.utils import assert_literal_value_valid


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

    runbook: Runbook = field(metadata={"description": "The runbook of the agent."})
    """The runbook of the agent."""

    version: str = field(metadata={"description": "The version of the agent."})
    """The version of the agent."""

    # TODO: this is worth thinking through more --- are "provider configs" a seperate
    # entity and we just pass strings to what's available?
    provider_configs: list[str] = field(
        metadata={"description": "The provider configs this agent can use."},
    )
    """The provider configs this agent can use."""

    action_packages: list[ActionPackage] = field(
        metadata={"description": "The action packages this agent uses."},
    )
    """The action packages this agent uses."""

    agent_architecture: AgentArchitecture = field(
        metadata={"description": "The architecture details for the agent."},
    )
    """The architecture details for the agent."""

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
        default_factory=datetime.now,
    )
    """The creation time of the agent."""

    updated_at: datetime = field(
        metadata={"description": "The last update time of the agent."},
        default_factory=datetime.now,
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

    def copy(self) -> Self:
        """Returns a deep copy of the agent."""
        from copy import deepcopy

        return Agent(
            name=self.name,
            description=self.description,
            user_id=self.user_id,
            runbook=self.runbook.copy(),
            version=self.version,
            provider_configs=self.provider_configs,
            action_packages=[pkg.copy() for pkg in self.action_packages],
            agent_architecture=self.agent_architecture.copy(),
            question_groups=[group.copy() for group in self.question_groups],
            observability_configs=[
                config.copy() for config in self.observability_configs
            ],
            created_at=self.created_at,
            updated_at=self.updated_at,
            mode=self.mode,
            agent_id=self.agent_id,
            extra=deepcopy(self.extra) if self.extra != {} else {},
        )

    def to_json_dict(self) -> dict:
        """Serializes the agent to a dictionary. Useful for JSON serialization."""
        return {
            "action_packages": [
                action_package.to_json_dict()
                for action_package in self.action_packages
            ],
            "agent_architecture": self.agent_architecture.to_json_dict(),
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "extra": self.extra,
            "mode": self.mode,
            "provider_configs": self.provider_configs,
            "name": self.name,
            "observability_configs": [
                observability_config.to_json_dict()
                for observability_config in self.observability_configs
            ],
            "question_groups": [
                question_group.to_json_dict()
                for question_group in self.question_groups
            ],
            "runbook": self.runbook.to_json_dict(),
            "agent_id": self.agent_id,
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
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
            ActionPackage.from_dict(action_package)
            for action_package in data.pop("action_packages", [])
        ]
        agent_architecture = AgentArchitecture.from_dict(
            data.pop("agent_architecture", {}),
        )
        observability_configs = [
            ObservabilityConfig.from_dict(observability_config)
            for observability_config in data.pop("observability_configs", [])
        ]
        question_groups = [
            QuestionGroup.from_dict(question_group)
            for question_group in data.pop("question_groups", [])
        ]
        runbook = Runbook.from_dict(data.pop("runbook", {}))

        # Parse datetime fields
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(
            action_packages=actions_packages,
            agent_architecture=agent_architecture,
            observability_configs=observability_configs,
            question_groups=question_groups,
            runbook=runbook,
            **data,
        )
