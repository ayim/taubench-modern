from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_spec.knowledge import KnowledgeStreams


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
