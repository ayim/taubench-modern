from dataclasses import dataclass, field
from typing import ClassVar, Literal

from agent_platform.core.agent import Agent
from agent_platform.core.mcp.mcp_server import MCPServer
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
    whitelist: str = field(default="")


@dataclass(frozen=True)
class MCPVariableCompat:
    type: Literal["string", "secret", "oauth2-secret", "data-server-info"]
    description: str | None = None
    provider: str | None = None
    scopes: list[str] | None = None
    value: str | None = None

    @classmethod
    def from_variable(cls, var, reveal_sensitive: bool = False):
        # Handle string (legacy, not a dict)
        if isinstance(var, str):
            return var if (reveal_sensitive or not var) else "**********"
        # Handle dataclass types
        t = getattr(var, "type", None)
        value = getattr(var, "value", None)
        masked_value = value if (reveal_sensitive or not value) else "**********"
        if t == "string":
            return cls(
                type="string",
                description=getattr(var, "description", None),
                value=masked_value,
            )
        elif t == "secret":
            return cls(
                type="secret",
                description=getattr(var, "description", None),
                value=masked_value,
            )
        elif t == "oauth2-secret":
            return cls(
                type="oauth2-secret",
                provider=getattr(var, "provider", None),
                scopes=getattr(var, "scopes", None),
                description=getattr(var, "description", None),
                value=masked_value,
            )
        elif t == "data-server-info":
            return cls(
                type="data-server-info",
                value=masked_value,
            )
        # fallback: string
        return str(var)


@dataclass(frozen=True)
class MCPServerCompat:
    name: str
    transport: str
    url: str | None = None
    headers: dict[str, str | MCPVariableCompat] | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str | MCPVariableCompat] | None = None
    cwd: str | None = None
    force_serial_tool_calls: bool = False

    @classmethod
    def from_mcp_server(cls, server: MCPServer, reveal_sensitive: bool = False):
        def mask_vars(vars_dict):
            if not vars_dict:
                return None
            result = {}
            for k, v in vars_dict.items():
                compat = MCPVariableCompat.from_variable(v, reveal_sensitive)
                result[k] = compat
            return result

        return cls(
            name=server.name,
            transport=server.transport,
            url=server.url,
            headers=mask_vars(server.headers),
            command=server.command,
            args=server.args,
            env=mask_vars(server.env),
            cwd=server.cwd,
            force_serial_tool_calls=server.force_serial_tool_calls,
        )


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
    SENSITIVE_KEYS: ClassVar[list[str]] = [
        "openai_api_key",
        "azure_api_key",
        "google_api_key",
        "groq_api_key",
        "anthropic_api_key",
        "chat_openai_api_key",
        "embeddings_openai_api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
        "snowflake_password",
    ]

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
    mcp_servers: list[MCPServerCompat] = field(default_factory=list)

    @classmethod
    def _convert_platform_config_to_legacy_model(  # noqa: PLR0912, C901
        cls,
        platform_configs: list[AnyPlatformParameters],
        reveal_sensitive: bool = False,
    ) -> dict:
        # TODO: more backwards compat, this dance will go away
        # when we have some good time to focus on studio integration
        # For now, if we don't round trip the "allow model during POST"
        # back to "render first platform_config as model", studio chokes

        # Fallback default to keep studio rendering happy
        model = {
            "provider": "OpenAI",
            "name": "gpt-4o",
            "config": {},
        }

        if len(platform_configs) <= 0:
            return model

        if platform_configs[0].kind not in cls.KIND_TO_PROVIDER:
            raise ValueError(f"Agent has invalid platform config kind: {platform_configs[0].kind}")

        model_config = platform_configs[0].model_dump()
        del model_config["kind"]

        # If we have an allowlist then the legacy model name will be the
        # first name in the allowlist. Otherwise, we use the kind
        # to provider mapping.
        model_name = None
        if platform_configs[0].models:
            first_provider = next(iter(platform_configs[0].models))
            first_name = platform_configs[0].models[first_provider][0]
            model_name = first_name
        else:
            model_name = cls.KIND_TO_LEGACY_MODEL[platform_configs[0].kind]

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
            model_config["embeddings_url"] = model_config["azure_generated_endpoint_url_embeddings"]
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

        # Mask sensitive API keys if requested
        if not reveal_sensitive:
            model_config = {
                k: "**********" if k in cls.SENSITIVE_KEYS else v for k, v in model_config.items()
            }

        return dict(
            provider=cls.KIND_TO_PROVIDER[platform_configs[0].kind],
            name=model_name,
            config=model_config,
        )

    @classmethod
    def from_agent(cls, agent: Agent, reveal_sensitive: bool = False) -> "AgentCompat":
        model = cls._convert_platform_config_to_legacy_model(
            agent.platform_configs,
            reveal_sensitive=reveal_sensitive,
        )

        # Mask runbook if reveal_sensitive is False
        runbook_text = agent.runbook_structured.raw_text
        if not reveal_sensitive and runbook_text:
            runbook_text = "**********"

        # Create masked runbook_structured if reveal_sensitive is False
        masked_runbook_structured = agent.runbook_structured
        if not reveal_sensitive:
            from agent_platform.core.runbook import Runbook

            masked_runbook_structured = Runbook(
                raw_text="**********" if agent.runbook_structured.raw_text else "",
                content=[],
            )

        langsmith_config = None
        if len(agent.observability_configs) > 0:
            obs_config = agent.observability_configs[0]
            langsmith_config = dict(
                api_key="**********" if not reveal_sensitive else obs_config.api_key,
                api_url=obs_config.api_url,
                project_name=obs_config.settings["project_name"],
            )

        masked_platform_configs = agent.platform_configs
        if not reveal_sensitive:
            masked_platform_configs = []
            for config in agent.platform_configs:
                config_dict = config.model_dump()
                # Remove kind field as it's init=False in the dataclass
                config_dict.pop("kind", None)
                # Mask sensitive keys in platform config
                for key in cls.SENSITIVE_KEYS:
                    if key in config_dict:
                        config_dict[key] = "**********"
                # Create a new config object with masked data
                masked_platform_configs.append(type(config).model_validate(config_dict))

        return cls(
            id=agent.agent_id,
            runbook=runbook_text,
            public=True,
            metadata=dict(
                mode=agent.mode,
                worker_config=(
                    agent.extra["worker-config"]
                    if "worker-config" in agent.extra
                    else agent.extra.get("worker_config", {})
                ),
                welcome_message=(
                    agent.extra["welcome-message"]
                    if "welcome-message" in agent.extra
                    else agent.extra.get("welcome-message", "")
                ),
                question_groups=agent.question_groups,
            ),
            model=model,
            advanced_config=dict(
                # Only legacy architecture corresponding to v2
                # agents is "agent" (we can't have "plan_execute" here)
                # NOTE: cleints should really start _not looking here_,
                # especially now that we have some other non-default
                # architectures.
                architecture="agent",
                reasoning="disabled",
                recursion_limit=100,
                langsmith=langsmith_config,
            ),
            name=agent.name,
            description=agent.description,
            user_id=agent.user_id,
            version=agent.version,
            runbook_structured=masked_runbook_structured,
            action_packages=[
                ActionPackageCompat(
                    name=ap.name,
                    organization=ap.organization,
                    version=ap.version,
                    url=ap.url,
                    api_key="**********"
                    if not reveal_sensitive and ap.api_key
                    else (ap.api_key.get_secret_value() if ap.api_key else None),
                    whitelist=",".join(ap.allowed_actions),
                )
                for ap in agent.action_packages
            ],
            mcp_servers=[
                MCPServerCompat.from_mcp_server(s, reveal_sensitive=reveal_sensitive)
                for s in agent.mcp_servers
            ],
            agent_architecture=agent.agent_architecture,
            question_groups=agent.question_groups,
            platform_configs=masked_platform_configs,
            observability_configs=agent.observability_configs,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            mode=agent.mode,
            agent_id=agent.agent_id,
            extra=agent.extra,
        )
