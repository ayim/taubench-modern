from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.agent_spec.knowledge import KnowledgeStreams


@dataclass(frozen=True)
class AgentPackageParsed:
    spec: dict[str, Any] = field(
        metadata={
            "description": "The parsed agent package specification.",
        }
    )
    """The parsed agent package specification."""

    runbook_text: str = field(
        metadata={
            "description": "The runbook text.",
        }
    )
    """The runbook text."""

    knowledge: Mapping[str, bytes] | KnowledgeStreams | None = field(
        default=None,
        metadata={
            "description": "The knowledge files, if requested (default: ``None``).",
        },
    )
    """The knowledge files, if requested (default: ``None``)."""
