from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import uuid4

from agent_platform_core.agent import Agent
from agent_platform_core.runbook import Runbook


@dataclass(frozen=True)
class UpsertAgentPayload(Agent):
    """Payload for upserting an agent."""

    runbook_raw_text: str = field(
        default="",
        metadata={"description": "The raw text of the runbook."},
    )
    """The raw text of the runbook."""

    runbook: Runbook = field(
        init=False, repr=False,
        metadata={"description": "The runbook of the agent."},
    )
    """The runbook of the agent."""

    user_id: str = field(
        init=False, repr=False,
        metadata={"description": "The ID of the user that owns the agent."},
    )
    """The ID of the user that owns the agent."""

    agent_id: str = field(
        init=False, repr=False,
        metadata={"description": "The ID of the agent."},
    )
    """The ID of the agent."""
    created_at: datetime = field(
        init=False, repr=False,
        metadata={"description": "The time the agent was created."},
    )
    """The time the agent was created."""

    updated_at: datetime = field(
        init=False, repr=False,
        metadata={"description": "The last time the agent was updated."},
    )
    """The last time the agent was updated."""

    def __post_init__(self):
        # Ensure runbook text is valid
        if not self.runbook_raw_text:
            raise ValueError("runbook_raw_text is required")

        object.__setattr__(self, "runbook", Runbook(raw_text=self.runbook_raw_text))

    @classmethod
    def to_agent(cls, payload: Self, user_id: str) -> Agent:
        return Agent(
            name=payload.name,
            version=payload.version,
            description=payload.description,
            runbook=payload.runbook,
            observability_configs=payload.observability_configs,
            question_groups=payload.question_groups,
            action_packages=payload.action_packages,
            mcp_servers=payload.mcp_servers,
            agent_architecture=payload.agent_architecture,
            platform_configs=payload.platform_configs,
            extra=payload.extra,
            user_id=user_id,
            agent_id=str(uuid4()),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
