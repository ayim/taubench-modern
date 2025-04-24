from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.agent import Agent


# TODO: purely for backwards compatibility
# work to be able to remove this
@dataclass(frozen=True)
class ActionPackageCompat:
    name: str = field(default="")
    organization: str = field(default="")
    version: str = field(default="")
    url: str | None = field(default=None)
    api_key: str | None = field(default=None)
    allowed_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentCompat(Agent):
    runbook: str = field(default="")
    id: str | None = field(default=None)
    public: bool = field(default=True)
    metadata: dict = field(default_factory=dict)
    advanced_config: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    mode: Literal["conversational", "worker"] = field(default="conversational")
    action_packages: list[ActionPackageCompat] = field(  # type: ignore (purposefully shadowing for backwards compatibility)
        default_factory=list,
    )

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentCompat":
        # Fallback default to keep studio rendering happy
        model = {
            "provider": "OpenAI",
            "model": "gpt-4o",
            "config": {
                "api_key": "UNSET",
            },
        }

        # TODO: more backwards compat, this dance will go away
        # when we have some good time to focus on studio integration
        # For now, if we don't round trip the "allow model during POST"
        # back to "render first platform_config as model", studio chokes
        if len(agent.platform_configs) > 0:
            kind_to_provider = {
                "openai": "OpenAI",
                "azure": "Azure",
                "cortex": "Snowflake Cortex AI",
                "bedrock": "Amazon",
                "groq": "Groq",
                "google": "Google",
                "anthropic": "Anthropic",
            }

            kind_to_legacy_model = {
                "openai": "gpt-4o",
                "azure": "gpt-4o",
                "cortex": "claude-3-5-sonnet",
                "bedrock": "claude-3-5-sonnet",
                "groq": "unknown",
                "google": "unknown",
                "anthropic": "claude-3-5-sonnet",
            }

            if agent.platform_configs[0].kind not in kind_to_provider:
                raise ValueError(
                    "Agent has invalid platform config kind: "
                    f"{agent.platform_configs[0].kind}"
                )

            model_config = agent.platform_configs[0].model_dump()
            del model_config["kind"]

            model = dict(
                provider=kind_to_provider[agent.platform_configs[0].kind],
                model=kind_to_legacy_model[agent.platform_configs[0].kind],
                config=model_config,
            )

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
            model=model,
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
            action_packages=[
                ActionPackageCompat(
                    name=ap.name,
                    organization=ap.organization,
                    version=ap.version,
                    url=ap.url,
                    api_key=ap.api_key.get_secret_value() if ap.api_key else None,
                    allowed_actions=ap.allowed_actions,
                )
                for ap in agent.action_packages
            ],
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
