from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.agent import Agent


@dataclass(frozen=True)
class AgentCompat(Agent):
    runbook: str = field(default="")
    id: str | None = field(default=None)
    public: bool = field(default=True)
    metadata: dict = field(default_factory=dict)
    advanced_config: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    mode: Literal["conversational", "worker"] = field(default="conversational")

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentCompat":
        return cls(
            id=agent.agent_id,
            runbook=agent.runbook_structured.raw_text,
            public=True,
            metadata=dict(
                mode=agent.mode,
                worker_config=(
                    agent.extra["worker_config"]
                    if "worker_config" in agent.extra
                    else {}
                ),
                welcome_message="",
                question_groups=agent.question_groups,
            ),
            advanced_config=dict(
                architecture=agent.agent_architecture.name,
                reasoning="disabled",
                recursion_limit=100,
                langsmith=(
                    dict(
                        api_key=agent.observability_configs[0].api_key,
                        api_url=agent.observability_configs[0].api_url,
                        project_name=agent.observability_configs[0].settings[
                            "project_name"
                        ],
                    )
                    if len(agent.observability_configs) > 0
                    else None
                ),
            ),
            name=agent.name,
            description=agent.description,
            user_id=agent.user_id,
            version=agent.version,
            runbook_structured=agent.runbook_structured,
            action_packages=agent.action_packages,
            mcp_servers=agent.mcp_servers,
            agent_architecture=agent.agent_architecture,
            question_groups=agent.question_groups,
            platform_configs=agent.platform_configs,
            observability_configs=agent.observability_configs,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            mode=agent.mode,
            agent_id=agent.agent_id,
            extra=agent.extra,
        )
