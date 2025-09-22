from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Self, cast
from uuid import uuid4

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent import AgentArchitecture
from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.architectures.resolver import (
    PlatformCandidateSet as ArchPlatformCandidateSet,
)
from agent_platform.core.architectures.resolver import (
    resolve_architecture as resolve_architecture_for_platforms,
)
from agent_platform.core.mcp import MCPServer
from agent_platform.core.platforms import AnyPlatformParameters
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.platforms.configs import (
    PlatformModelConfigs,
    resolve_provider_from_model_name,
)
from agent_platform.core.runbook import Runbook
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(frozen=True)
class PatchAgentPayload:
    """Payload for patching an agent."""

    name: str = field(metadata={"description": "The name of the agent."})
    """The name of the agent."""

    description: str = field(
        metadata={"description": "The description of the agent."},
    )


@dataclass
class UpsertAgentPayload:
    """Payload for upserting an agent."""

    name: str = field(metadata={"description": "The name of the agent."})
    """The name of the agent."""

    description: str = field(
        metadata={"description": "The description of the agent."},
    )
    """The description of the agent."""

    version: str = field(metadata={"description": "The version of the agent."})
    """The version of the agent."""

    user_id: str | None = field(
        default=None,
        metadata={"description": "The id of the user that created the agent."},
    )
    """The id of the user that created the agent."""

    platform_configs: list[dict] = field(
        metadata={"description": "The platform configs this agent can use."},
        default_factory=list,
    )
    """The platform configs this agent can use."""

    agent_architecture: AgentArchitecture | None = field(
        default=None,
        metadata={"description": "The architecture details for the agent."},
    )
    """The architecture details for the agent."""

    runbook: str | None = field(
        default=None,
        metadata={"description": "The raw text of the runbook."},
    )
    """The raw text of the runbook."""

    structured_runbook: Runbook | None = field(
        default=None,
        metadata={"description": "The structured runbook of the agent."},
    )
    """The structured runbook of the agent."""

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

    mcp_server_ids: list[str] = field(
        metadata={
            "description": "The IDs of Model Context Protocol (MCP) servers this agent uses.",
        },
        default_factory=list,
    )
    """The IDs of Model Context Protocol (MCP) servers this agent uses."""

    selected_tools: SelectedTools = field(
        metadata={
            "description": "Configuration for tools selected for this agent.",
        },
        default_factory=SelectedTools,
    )
    """Configuration for tools selected for this agent."""

    platform_params_ids: list[str] = field(
        metadata={
            "description": "The IDs of platform params this agent uses.",
        },
        default_factory=list,
    )
    """The IDs of platform params this agent uses."""

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

    mode: Literal["conversational", "worker"] = field(
        metadata={"description": "The mode of the agent."},
        default="conversational",
    )
    """The mode of the agent."""

    extra: dict[str, Any] = field(
        metadata={"description": "Extra fields for the agent."},
        default_factory=dict,
    )
    """Extra fields for the agent."""

    agent_settings: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Settings that control the agent's behavior."},
    )
    """Settings that control the agent's behavior."""

    document_intelligence: Literal["v2"] | None = field(
        default=None,
        metadata={"description": "The document intelligence version to use."},
    )
    """The document intelligence version to use."""

    id: str | None = field(
        default=None,
        metadata={
            "description": ("The ID of the agent (alias of agent_id for backwards compatibility)."),
        },
    )
    """The ID of the agent (alias of agent_id for backwards compatibility)."""

    agent_id: str | None = field(
        default=None,
        metadata={"description": "The ID of the agent."},
    )
    """The ID of the agent."""

    created_at: datetime | None = field(
        default=None,
        metadata={"description": "The time the agent was created."},
    )
    """The time the agent was created."""

    advanced_config: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": ("Advanced configuration for the agent (backward compatibility)."),
        },
    )
    """Advanced configuration for the agent (backward compatibility)."""

    metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "description": ("Metadata for the agent (backward compatibility)."),
        },
    )
    """Metadata for the agent (backward compatibility)."""

    model: dict[str, Any] | None = field(
        default=None,
        metadata={
            "description": ("Model for the agent (backward compatibility)."),
        },
    )
    """Model for the agent (backward compatibility)."""

    public: bool = field(
        default=True,
        metadata={"description": "Ignored. Backward compatibility only."},
    )
    """Ignored. Backward compatibility only."""

    def _handle_legacy_architecture(self):
        """Handle backward compatibility for 'architecture' in advanced_config."""
        if "architecture" in self.advanced_config:
            # Instead of mapping _only_ to default arch, if (in the legacy payload)
            # we're getting a seemingly non-legacy architecture, we'll use that instead
            architecture = self.advanced_config["architecture"]
            if not architecture.startswith("agent_platform.architectures."):
                architecture = "agent_platform.architectures.default"

            self.agent_architecture = AgentArchitecture.model_validate(
                {
                    "name": architecture,
                    "version": "1.0.0",
                }
            )

            del self.advanced_config["architecture"]

    def _handle_legacy_langsmith(self):
        """Handle backward compatibility for 'langsmith' in advanced_config."""
        if "langsmith" in self.advanced_config:
            ls_config = self.advanced_config["langsmith"]
            if ls_config is not None and "api_key" in ls_config:
                self.observability_configs = [
                    ObservabilityConfig.model_validate(
                        {
                            "type": "langsmith",
                            "api_key": ls_config["api_key"],
                            "api_url": ls_config["api_url"],
                            "settings": {
                                "project_name": ls_config["project_name"],
                            },
                        }
                    )
                ]
            del self.advanced_config["langsmith"]

    def _handle_legacy_mode(self):
        """Handle backward compatibility for 'mode' in metadata."""
        if "mode" in self.metadata:
            self.mode = self.metadata["mode"]
            del self.metadata["mode"]

    def _handle_legacy_welcome_message(self):
        """Handle backward compatibility for 'welcome_message' in metadata."""
        if "welcome_message" in self.metadata:
            self.extra = {
                **self.extra,
                "welcome_message": self.metadata["welcome_message"],
            }
            del self.metadata["welcome_message"]

    def _handle_legacy_worker_config(self):
        """Handle backward compatibility for 'worker_config' in metadata."""
        key = None
        if "worker_config" in self.metadata:
            key = "worker_config"
        elif "worker-config" in self.metadata:
            key = "worker-config"

        if key is not None:
            worker_cfg = self.metadata[key]
            self.extra = {
                **self.extra,
                "worker_config": worker_cfg,
            }
            del self.metadata[key]

    def _handle_legacy_question_groups(self):
        """Handle backward compatibility for 'question_groups' in metadata."""
        if self.question_groups:
            if "question_groups" in self.metadata:
                del self.metadata["question_groups"]
            return

        if "question_groups" in self.metadata and isinstance(
            self.metadata["question_groups"], list
        ):
            self.question_groups = [
                QuestionGroup.model_validate(group) for group in self.metadata["question_groups"]
            ]
            del self.metadata["question_groups"]

    def _legacy_model_dict_to_allowlist(
        self,
        model_dict: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Convert a legacy model dictionary to an allowlist dictionary.

        Given a legacy provider/name string, convert it to an allowlist dictionary
        that permits only that model. If the model name matches 'provider/name', then
        we will use the provider/ prefix instead of the "provider" key (as the legacy
        provider key is really more "platform" level than provider level).

        Args:
            model_dict: The model dictionary to convert.

        Returns:
            The allowlist dictionary, or None if the model dictionary is invalid.
        """
        if "provider" not in model_dict or not model_dict["provider"]:
            return None
        if "name" not in model_dict or not model_dict["name"]:
            return None

        name = model_dict["name"]
        if "/" in name:
            provider, name = name.split("/", 1)
        else:
            provider = model_dict["provider"].lower()

        provider = resolve_provider_from_model_name(name, provider)

        return {
            provider: [name],
        }

    def _handle_legacy_model_openai(self):
        """Handle backward compatibility for 'model' field with OpenAI."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "OpenAI":
            return

        params_to_keep = [
            "openai_api_key",
        ]
        params = {
            "openai_api_key": "UNSET",
        }
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        self.platform_configs = [
            {
                "kind": "openai",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _split_azure_url(self, url: str) -> tuple[str, str, str]:
        """Split an Azure URL into endpoint, deployment name, and api version."""
        assert "/openai/deployments/" in url, (
            f"Invalid azure url, must contain /openai/deployments/: {url}"
        )
        assert "chat/completions" in url or "embeddings" in url, (
            f"Invalid azure url, must contain chat/completions or embeddings: {url}"
        )
        assert "?api-version=" in url, f"Invalid azure url, must contain ?api-version=: {url}"

        parts = url.split("/openai/deployments/")
        if len(parts) > 1:
            endpoint, rest = parts
            parts = rest.split("/chat/completions?api-version=")
            if len(parts) > 1:
                deployment_name, api_version = parts
                return endpoint, deployment_name, api_version
            else:
                parts = rest.split("/embeddings?api-version=")
                if len(parts) > 1:
                    deployment_name, api_version = parts
                    return endpoint, deployment_name, api_version

                raise ValueError("Invalid azure url: failed to get deployment name and api version")
        else:
            raise ValueError("Invalid azure url: failed to get endpoint from url")

    def _handle_legacy_model_azure(self):
        """Handle backward compatibility for 'model' field with Azure."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Azure":
            return

        params_to_keep = [
            "chat_url",
            "chat_openai_api_key",
            "embeddings_url",
            "embeddings_openai_api_key",
        ]
        params = {
            "chat_url": "https://UNSET.openai.azure.com/openai/deployments/UNSET/chat/completions?api-version=2025-01-01",
            "chat_openai_api_key": "UNSET",
            "embeddings_url": "https://UNSET.openai.azure.com/openai/deployments/UNSET/embeddings?api-version=2025-01-01",
            "embeddings_openai_api_key": "UNSET",
            "azure_model_backing_deployment_name": self.model["name"],
        }
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        # Legacy: chat_url -> azure_endpoint_url, azure_deployment_name
        # and azure_api_version
        if params.get("chat_url"):
            endpoint, deployment_name, api_version = self._split_azure_url(
                params["chat_url"],
            )
            params["azure_endpoint_url"] = endpoint
            params["azure_deployment_name"] = deployment_name
            params["azure_api_version"] = api_version

        # Now same for embeddings_url (just get the deployment name)
        if params.get("embeddings_url"):
            _, deployment_name, _ = self._split_azure_url(params["embeddings_url"])
            params["azure_deployment_name_embeddings"] = deployment_name

        # Legacy: chat_openai_api_key -> azure_api_key
        if "chat_openai_api_key" in params:
            params["azure_api_key"] = params["chat_openai_api_key"]

        # Remove chat_openai_api_key if present
        params.pop("chat_openai_api_key", None)
        # Remove embeddings_openai_api_key if present
        params.pop("embeddings_openai_api_key", None)
        # Remove chat_url if present
        params.pop("chat_url", None)
        # Remove embeddings_url if present
        params.pop("embeddings_url", None)

        self.platform_configs = [
            {
                "kind": "azure",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _handle_legacy_model_ollama(self):
        """Handle backward compatibility for 'model' field with Ollama."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Ollama":
            return

        raise NotImplementedError("Ollama is not supported yet.")

    def _handle_legacy_model_anthropic(self):
        """Handle backward compatibility for 'model' field with Anthropic."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Anthropic":
            return

        raise NotImplementedError("Anthropic is not supported yet.")

    def _handle_legacy_model_bedrock(self):
        """Handle backward compatibility for 'model' field with Bedrock."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Amazon":
            return

        params_to_keep = [
            "aws_access_key_id",
            "aws_secret_access_key",
            "region_name",
        ]
        params = {
            "aws_access_key_id": "UNSET",
            "aws_secret_access_key": "UNSET",
            "region_name": "UNSET",
        }
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        self.platform_configs = [
            {
                "kind": "bedrock",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _handle_legacy_model_snowflake(self):
        """Handle backward compatibility for 'model' field with Snowflake Cortex AI."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Snowflake Cortex AI":
            return

        params_to_keep = [
            "snowflake_username",
            "snowflake_password",
            "snowflake_account",
            "snowflake_warehouse",
            "snowflake_database",
            "snowflake_schema",
            "snowflake_role",
        ]
        params = {}
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        self.platform_configs = [
            {
                "kind": "cortex",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _handle_legacy_model_google(self):
        """Handle backward compatibility for 'model' field with Google."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Google":
            return

        params_to_keep = [
            "google_api_key",
        ]
        params = {
            "google_api_key": "UNSET",
        }
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        self.platform_configs = [
            {
                "kind": "google",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _handle_legacy_model_groq(self):
        """Handle backward compatibility for 'model' field with Groq."""
        if not self.model or "provider" not in self.model:
            return
        if self.model["provider"] != "Groq":
            return

        params_to_keep = [
            "groq_api_key",
        ]
        params = {
            "groq_api_key": "UNSET",
        }
        if "config" in self.model:
            for param in params_to_keep:
                if param in self.model["config"]:
                    params[param] = self.model["config"][param]

        self.platform_configs = [
            {
                "kind": "groq",
                **params,
                "models": self._legacy_model_dict_to_allowlist(self.model),
            },
            *self.platform_configs,
        ]
        self.model = None

    def _handle_legacy_model(self):
        """Handle backward compatibility for 'model' field."""
        if self.model:
            # No temperature from clients anymore (odd legacy choice)
            if "config" in self.model and "temperature" in self.model["config"]:
                del self.model["config"]["temperature"]

            self._handle_legacy_model_openai()
            self._handle_legacy_model_azure()
            self._handle_legacy_model_ollama()
            self._handle_legacy_model_anthropic()
            self._handle_legacy_model_bedrock()
            self._handle_legacy_model_snowflake()
            self._handle_legacy_model_google()
            self._handle_legacy_model_groq()

    def _validate_architecture_based_on_platform_configs(
        self, platform_configs: list[AnyPlatformParameters]
    ) -> AgentArchitecture:
        """Resolve a compatible architecture for the given platform configs."""
        if not platform_configs:
            # Type guard: ensured non-None in __post_init__
            assert self.agent_architecture is not None
            return self.agent_architecture

        platform_sets: list[ArchPlatformCandidateSet] = []
        for idx, cfg in enumerate(platform_configs):
            raw_cfg = self.platform_configs[idx] if idx < len(self.platform_configs) else {}
            explicit_allowlist = isinstance(raw_cfg, dict) and ("models" in raw_cfg)
            platform_sets.append(
                ArchPlatformCandidateSet(config=cfg, explicit_allowlist=explicit_allowlist)
            )

        # Type guard: ensured non-None in __post_init__
        assert self.agent_architecture is not None
        return resolve_architecture_for_platforms(
            self.agent_architecture,
            platform_sets,
            cfg_provider=PlatformModelConfigs,
        )

    def __post_init__(self):
        # Handle backward compatibility conversions first
        self._handle_legacy_architecture()
        self._handle_legacy_langsmith()
        self._handle_legacy_mode()
        self._handle_legacy_welcome_message()
        self._handle_legacy_worker_config()
        self._handle_legacy_question_groups()
        self._handle_legacy_model()

        # --- Validations and final adjustments ---

        # Make sure mode is valid
        assert_literal_value_valid(self, "mode")

        # Make sure agent_architecture is present after potential legacy conversion
        if self.agent_architecture is None:
            raise ValueError(
                "agent_architecture is required but was not provided: "
                "or derived from legacy fields.",
            )

        # Ensure runbook text is valid
        if not self.runbook and not self.structured_runbook:
            raise ValueError("A runbook or structured runbook is required")

        # Null out runbook if structured runbook is present (prefer structured)
        if self.structured_runbook:
            self.runbook = None

        # If agent_id is set, we take that over id for consistency
        if self.agent_id:
            self.id = self.agent_id
        # If only id is set, ensure agent_id also gets this value
        elif self.id and not self.agent_id:
            self.agent_id = self.id

        # Ensure platform configs are valid dictionaries
        for config in self.platform_configs:
            if not isinstance(config, dict):
                raise ValueError("platform_configs must be a list of dictionaries")

    def model_dump(self, include_legacy: bool = False) -> dict:
        as_dict = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "user_id": self.user_id,
            "platform_configs": self.platform_configs,
            "agent_architecture": (
                self.agent_architecture.model_dump() if self.agent_architecture else None
            ),
            "runbook": self.runbook,
            "structured_runbook": (
                self.structured_runbook.model_dump() if self.structured_runbook else None
            ),
            "action_packages": [pkg.model_dump() for pkg in self.action_packages],
            "mcp_servers": [server.model_dump() for server in self.mcp_servers],
            "mcp_server_ids": self.mcp_server_ids,
            "platform_params_ids": self.platform_params_ids,
            "question_groups": [group.model_dump() for group in self.question_groups],
            "observability_configs": [config.model_dump() for config in self.observability_configs],
            "mode": self.mode,
            "extra": self.extra,
            "agent_settings": self.agent_settings,
            "id": self.id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "advanced_config": self.advanced_config,
            "metadata": self.metadata,
            "model": self.model,
            "public": self.public,
        }

        if not include_legacy:
            as_dict.pop("advanced_config", None)
            as_dict.pop("metadata", None)
            as_dict.pop("model", None)
            as_dict.pop("public", None)
            as_dict.pop("id", None)  # agent_id is preferred

        return as_dict

    @classmethod
    def to_agent(
        cls,
        payload: Self,
        user_id: str,
        agent_id: str | None = None,
    ) -> Agent:
        # Make sure agent_architecture is present
        if payload.agent_architecture is None:
            raise ValueError("agent_architecture is required")

        platform_configs = [
            cast(AnyPlatformParameters, PlatformParameters.model_validate(config))
            for config in payload.platform_configs
        ]

        # If for any of the platform configs, there's an allowlist
        # Check to see if any of the models in the allowlist have an
        # architecture requirement that is not met by the agent_architecture
        validated_architecture = payload._validate_architecture_based_on_platform_configs(
            platform_configs
        )

        def _get_mode(payload: Self) -> Literal["conversational", "worker"] | None:
            try:
                mode = getattr(payload, "mode", None)
                if mode in ("conversational", "worker"):
                    return mode
                metadata = getattr(payload, "metadata", {})
                if isinstance(metadata, dict):
                    mode = metadata.get("mode")
                    if mode in ("conversational", "worker"):
                        return mode
            except Exception:
                pass

            return None

        maybe_mode = _get_mode(payload=payload)

        metadata = getattr(payload, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
        metadata_without_mode = {k: v for k, v in payload.metadata.items() if k != "mode"}

        extra = getattr(payload, "extra", None)
        if not isinstance(extra, dict):
            extra = {}

        return Agent(
            name=payload.name,
            mode=maybe_mode if maybe_mode is not None else "conversational",
            version=payload.version,
            description=payload.description,
            runbook_structured=(
                Runbook(raw_text=payload.runbook, content=[])
                if payload.runbook
                else (
                    payload.structured_runbook
                    or Runbook(raw_text="You are a helpful assistant.", content=[])
                )
            ),
            observability_configs=payload.observability_configs,
            question_groups=payload.question_groups,
            action_packages=payload.action_packages,
            mcp_servers=payload.mcp_servers,
            mcp_server_ids=payload.mcp_server_ids,
            selected_tools=payload.selected_tools,
            platform_params_ids=payload.platform_params_ids,
            agent_architecture=validated_architecture,
            platform_configs=platform_configs,
            extra={
                **metadata_without_mode,
                **extra,
                "agent_settings": payload.agent_settings or {},
                "document_intelligence": payload.document_intelligence,
            },
            user_id=user_id,
            agent_id=(
                # We prefer an agent_id passed in
                agent_id
                # Otherwise, use the agent_id from the payload
                or payload.agent_id
                # Otherwise, use the id from the payload
                or payload.id
                # Otherwise, generate a new one
                or str(uuid4())
            ),
            created_at=payload.created_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @classmethod
    def model_validate(cls, data: Any) -> "UpsertAgentPayload":
        """Validate and convert dictionary data to UpsertAgentPayload instance."""
        # Make a copy to avoid modifying the original data
        validated_data = data.copy() if isinstance(data, dict) else {}

        # Convert agent_architecture from dict to AgentArchitecture object if needed
        if "agent_architecture" in validated_data and isinstance(
            validated_data["agent_architecture"], dict
        ):
            validated_data["agent_architecture"] = AgentArchitecture.model_validate(
                validated_data["agent_architecture"]
            )

        # Convert structured_runbook from dict to Runbook object if needed
        if "structured_runbook" in validated_data and isinstance(
            validated_data["structured_runbook"], dict
        ):
            validated_data["structured_runbook"] = Runbook.model_validate(
                validated_data["structured_runbook"]
            )

        # Convert action_packages from list of dicts to list of ActionPackage objects
        if "action_packages" in validated_data and isinstance(
            validated_data["action_packages"], list
        ):
            validated_data["action_packages"] = [
                ActionPackage.model_validate(pkg) if isinstance(pkg, dict) else pkg
                for pkg in validated_data["action_packages"]
            ]

        # Convert mcp_servers from list of dicts to list of MCPServer objects
        if "mcp_servers" in validated_data and isinstance(validated_data["mcp_servers"], list):
            validated_data["mcp_servers"] = [
                MCPServer.model_validate(server) if isinstance(server, dict) else server
                for server in validated_data["mcp_servers"]
            ]

        # Convert question_groups from list of dicts to list of QuestionGroup objects
        if "question_groups" in validated_data and isinstance(
            validated_data["question_groups"], list
        ):
            validated_data["question_groups"] = [
                QuestionGroup.model_validate(group) if isinstance(group, dict) else group
                for group in validated_data["question_groups"]
            ]

        # Convert observability_configs from list of dicts to list of ObservabilityConfig objects
        if "observability_configs" in validated_data and isinstance(
            validated_data["observability_configs"], list
        ):
            validated_data["observability_configs"] = [
                ObservabilityConfig.model_validate(config) if isinstance(config, dict) else config
                for config in validated_data["observability_configs"]
            ]

        # Convert selected_tools from dict to SelectedTools object
        if "selected_tools" in validated_data and isinstance(
            validated_data["selected_tools"], dict
        ):
            validated_data["selected_tools"] = SelectedTools.model_validate(
                validated_data["selected_tools"]
            )

        return cls(**validated_data)
