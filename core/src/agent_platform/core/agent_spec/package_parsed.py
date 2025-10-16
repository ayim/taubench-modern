from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_spec.knowledge import KnowledgeStreams


@dataclass(frozen=True)
class ActionPackageParsed:
    """
    Parsed action package.
    Example:
    - name: Control Room Test
      organization: MyActions
      type: folder
      version: 0.0.1
      whitelist: get_time_now
      path: MyActions/control-room-test/0.0.1
    """

    name: str = field(
        metadata={"description": "Name of the action package."},
        default="",
    )
    """Name of the action package."""

    organization: str = field(
        metadata={"description": "Organization of the action package."}, default=""
    )
    """Organization of the action package."""

    type: Literal["folder", "zip"] = field(
        metadata={"description": "Type of the action package."},
        default="zip",
    )
    """Type of the action package."""

    version: str = field(metadata={"description": "Version of the action package."}, default="")
    """Version of the action package."""

    whitelist: str = field(metadata={"description": "Whitelist of the action package."}, default="")
    """Whitelist of the action package."""

    path: str = field(metadata={"description": "Path of the action package."}, default="")
    """Path of the action package."""

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "organization": self.organization,
            "type": self.type,
            "version": self.version,
            "whitelist": self.whitelist,
            "path": self.path,
        }

    @classmethod
    def model_validate(cls, data: Any) -> "ActionPackageParsed":
        return cls(
            name=data.get("name", ""),
            organization=data.get("organization", ""),
            type=data.get("type", "zip"),
            version=data.get("version", ""),
            whitelist=data.get("whitelist", ""),
            path=data.get("path", ""),
        )


@dataclass(frozen=True)
class AgentPackageParsed:
    spec: dict[str, Any] = field(
        metadata={
            "description": "The parsed agent package specification.",
            "default": {},
        }
    )
    """The parsed agent package specification."""

    runbook_text: str = field(
        metadata={
            "description": "The runbook text.",
            "default": "",
        }
    )
    """The runbook text."""

    knowledge: Mapping[str, bytes] | KnowledgeStreams | None = field(
        default=None,
        metadata={
            "description": "The knowledge files, if requested (default: ``None``).",
            "default": None,
        },
    )
    """The knowledge files, if requested (default: ``None``)."""

    question_groups: list[QuestionGroup] = field(
        default_factory=list,
        metadata={
            "description": "The question groups of the agent (from agent.metadata).",
            "default": [],
        },
    )
    """The question groups of the agent (from agent.metadata)."""

    conversation_starter: str | None = field(
        default=None,
        metadata={
            "description": "The conversation starter, if requested (default: ``None``).",
            "default": None,
        },
    )
    """The conversation starter, if requested (default: ``None``)."""

    welcome_message: str | None = field(
        default=None,
        metadata={
            "description": "The welcome message, if requested (default: ``None``).",
            "default": None,
        },
    )
    """The welcome message, if requested (default: ``None``)."""

    agent_settings: dict[str, Any] | None = field(
        default=None,
        metadata={
            "description": "The agent settings, if requested (default: ``None``).",
            "default": None,
        },
    )
    """The agent settings, if requested (default: ``None``)."""

    action_packages: list[ActionPackageParsed] = field(
        default_factory=list,
        metadata={
            "description": "The action packages of the agent (from agent.action-packages).",
            "default": [],
        },
    )
    """The action packages of the agent (from agent.action-packages)."""

    semantic_data_models: Mapping[str, dict[str, Any]] | None = field(
        default=None,
        metadata={
            "description": (
                "The semantic data models from semantic-data-models/ folder, "
                "if present (default: ``None``). Maps filename to SDM content."
            ),
            "default": None,
        },
    )
    """The semantic data models from semantic-data-models/ folder, if present.

    Maps filename to SDM content (default: ``None``)."""
