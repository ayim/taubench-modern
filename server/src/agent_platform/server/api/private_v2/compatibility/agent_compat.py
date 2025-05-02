from dataclasses import dataclass, field
from typing import ClassVar, Literal

from agent_platform.core.agent import Agent
from agent_platform.core.platforms import AnyPlatformParameters


# TODO: purely for backwards compatibility
# work to be able to remove this
@dataclass(frozen=True)
class ActionPackageCompat:
    name: str = field(default="")
    organization: str = field(default="")
    version: str = field(default="")
    url: str | None = field(default=None)
    api_key: str | None = field(default=None)
    whitelist: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentCompat(Agent):
    KIND_TO_PROVIDER: ClassVar[dict[str, str]] = {
        "openai": "OpenAI",
        "azure": "Azure",
        "cortex": "Snowflake Cortex AI",
        "bedrock": "Amazon",
        "groq": "Groq",
        "google": "Google",
        "anthropic": "Anthropic",
    }
    KIND_TO_LEGACY_MODEL: ClassVar[dict[str, str]] = {
        "openai": "gpt-4o",
        "azure": "gpt-4o",
        "cortex": "claude-3-5-sonnet",
        "bedrock": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "groq": "unknown",
        "google": "unknown",
        "anthropic": "claude-3-5-sonnet",
    }

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
    def _convert_platform_config_to_legacy_model(  # noqa: C901
        cls,
        platform_configs: list[AnyPlatformParameters],
    ) -> dict:
        # TODO: more backwards compat, this dance will go away
        # when we have some good time to focus on studio integration
        # For now, if we don't round trip the "allow model during POST"
        # back to "render first platform_config as model", studio chokes

        # Fallback default to keep studio rendering happy
        model = {
            "provider": "OpenAI",
            "model": "gpt-4o",
            "config": {},
        }

        if len(platform_configs) <= 0:
            return model

        if platform_configs[0].kind not in cls.KIND_TO_PROVIDER:
            raise ValueError(
                f"Agent has invalid platform config kind: {platform_configs[0].kind}"
            )

        model_config = platform_configs[0].model_dump()
        del model_config["kind"]

        # Handle legacy: chat_url and embeddings_url for Azure
        if "azure_endpoint_url" in model_config:
            del model_config["azure_endpoint_url"]
        if "azure_deployment_name" in model_config:
            del model_config["azure_deployment_name"]
        if "azure_api_version" in model_config:
            del model_config["azure_api_version"]
        if "azure_deployment_name_embeddings" in model_config:
            del model_config["azure_deployment_name_embeddings"]
        if "azure_generated_endpoint_url" in model_config:
            model_config["chat_url"] = model_config["azure_generated_endpoint_url"]
            del model_config["azure_generated_endpoint_url"]
        if "azure_generated_endpoint_url_embeddings" in model_config:
            model_config["embeddings_url"] = model_config[
                "azure_generated_endpoint_url_embeddings"
            ]
            del model_config["azure_generated_endpoint_url_embeddings"]

        # Handle legacy: chat_openai_api_key -> azure_api_key
        if "azure_api_key" in model_config:
            model_config["chat_openai_api_key"] = model_config["azure_api_key"]
            model_config["embeddings_openai_api_key"] = model_config["azure_api_key"]
            del model_config["azure_api_key"]

        # Handle legacy: Bedrock needs 'service-name'
        if "region_name" in model_config:
            model_config["service_name"] = "bedrock-runtime"

        # Remove UNSET values from model_config (on agent import right now
        # values are UNSET from legacy setup because a PUT comes in with
        # actual config values from studio later... ugh)
        model_config = {k: v for k, v in model_config.items() if v != "UNSET"}

        return dict(
            provider=cls.KIND_TO_PROVIDER[platform_configs[0].kind],
            model=cls.KIND_TO_LEGACY_MODEL[platform_configs[0].kind],
            config=model_config,
        )

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentCompat":
        model = cls._convert_platform_config_to_legacy_model(
            agent.platform_configs,
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
                # Only legacy architecture corresponding to v2
                # agents is "agent" (we can't have "plan_execute" here)
                architecture="agent",
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
                    whitelist=ap.whitelist,
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
