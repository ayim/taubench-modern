from enum import Enum
from io import StringIO
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ruamel.yaml import YAML

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent, QuestionGroup
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.utils import create_action_package_path
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.mcp.mcp_types import MCPUnionOfVariableTypes, mcp_redacted_variable_from_value
from agent_platform.core.platforms.legacy import convert_platform_config_to_legacy_model
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools


def _model_to_yaml(model: BaseModel, *, exclude_none: bool = True) -> str:
    """Serialize a Pydantic model to YAML format.

    Args:
        model: The Pydantic model to serialize.
        exclude_none: Whether to exclude fields with None values from the output.
            Defaults to True.

    Returns:
        A YAML string representation of the model.
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = 4096  # Prevent line wrapping

    # Convert model to dict with aliases
    data = model.model_dump(by_alias=True, exclude_none=exclude_none)

    # Write to string buffer
    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


# @TODO:
# Consider bringing types and models from other core packages.
# This would result in stronger coupling between Agent Packages logic and other modules,
# so it needs to be assessed properly first.
# Note that for simplicity, we are already pulling in MCPDiscriminatedUnion - this can be replaced
# with a dedicated type later if needs be.
SpecAgentModelProvider = str
SpecAgentReasoning = Literal["disabled", "enabled", "verbose"]
SpecMCPTransport = Literal["auto", "streamable-http", "sse", "stdio"]
SpecActionPackageType = Literal["zip", "folder"]
SpecWorkerMode = Literal["conversational", "worker"]
SpecVersion = Literal["v2", "v2.1", "v3"]
SpecDocumentIntelligence = Literal["v2", "v2.1"]


DEFAULT_AGENT_PACKAGE_EXCLUDE = [
    "./.git/**",
    "./.vscode/**",
    "./devdata/**",
    "./output/**",
    "./venv/**",
    "./.venv/**",
    "./**/.env",
    "./**/.DS_Store",
    "./**/*.pyc",
    "./*.zip",
]

DEFAULT_AGENT_PACKAGE_SPEC_VERSION: Literal["v2"] = "v2"
# The ID of the agent used for comparison purposes
DEFAULT_AGENT_TEMP_ID = "default_agent_temp_id"
DEFAULT_AGENT_TEMP_USER_ID = "default_agent_temp_user_id"


class AgentPackageSpecFileFields(Enum):
    """Fields of Agent Package Spec that map to files in the Agent Package.

    Maps field_path patterns from the diff to logical file categories:
        - spec: agent-spec.yaml
        - runbook: runbook.md
        - runbook_structured: runbook.md
        - conversation_guide: conversation-guide.yaml
        - question_groups: conversation-guide.yaml
        - semantic_data_models: semantic-data-models/ directory
    """

    spec = "spec"
    runbook = "runbook"
    runbook_structured = "runbook_structured"
    question_groups = "question_groups"
    conversation_guide = "conversation_guide"
    semantic_data_models = "semantic_data_models"


class SpecAgentModel(BaseModel):
    provider: str
    name: str


class SpecActionPackage(BaseModel):
    name: str
    organization: str
    version: str
    type: SpecActionPackageType | None = None
    whitelist: str | None = None
    path: str | None = None

    @classmethod
    def to_agent_action_packages(cls, action_packages: list["SpecActionPackage"]) -> list[ActionPackage]:
        return [
            ActionPackage(
                name=action_package.name,
                organization=action_package.organization,
                version=action_package.version,
                url=None,
                api_key=None,
                allowed_actions=action_package.whitelist.split(",") if action_package.whitelist else [],
            )
            for action_package in action_packages
        ]


class SpecKnowledge(BaseModel):
    name: str
    embedded: bool
    digest: str | None = None


class SpecSemanticDataModel(BaseModel):
    name: str


class SpecMCPServer(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    name: str
    transport: SpecMCPTransport | None = None
    description: str | None = None
    url: str | None = None
    headers: dict[str, MCPUnionOfVariableTypes] | None = None
    command_line: list[str] | None = Field(default=None, alias="command-line")
    env: dict[str, MCPUnionOfVariableTypes] | None = None
    cwd: str | None = None
    force_serial_tool_calls: bool | None = Field(default=False, alias="force-serial-tool-calls")

    @classmethod
    def from_mcp_server(cls, server: MCPServer):
        def mask_vars(vars_dict):
            if not vars_dict:
                return None
            return {k: mcp_redacted_variable_from_value(v) for k, v in vars_dict.items()}

        # Combine command and args into command_line list
        command_line = None
        if server.command:
            command_line = [server.command]
            if server.args:
                command_line.extend(server.args)

        return cls.model_validate(
            {
                "name": server.name,
                "transport": server.transport,
                # Description is not present in MCPServer and was never sent via the API
                "description": None,
                "url": server.url,
                "headers": mask_vars(server.headers),
                "command-line": command_line,
                "env": mask_vars(server.env),
                "cwd": server.cwd,
                "force-serial-tool-calls": server.force_serial_tool_calls,
            }
        )

    @classmethod
    def to_mcp_server(cls, mcp_servers: list["SpecMCPServer"] | None) -> list[MCPServer]:
        # Convert MCP servers
        result: list[MCPServer] = []
        for mcp in mcp_servers or []:
            # Build command and args from command_line
            command = None
            args: list[str] = []
            if mcp.command_line:
                command = mcp.command_line[0] if mcp.command_line else None
                args = list[str](mcp.command_line[1:]) if len(mcp.command_line) > 1 else []

            result.append(
                MCPServer(
                    name=mcp.name,
                    url=mcp.url,
                    command=command,
                    args=args,
                    cwd=mcp.cwd,
                    transport=mcp.transport or "auto",
                    headers=mcp.headers,
                    env=mcp.env,
                    force_serial_tool_calls=mcp.force_serial_tool_calls or False,
                )
            )
        return result


class SpecDockerMcpGateway(BaseModel):
    catalog: str | None = None
    servers: dict[str, dict[str, Any]]


# @TODO: This is a legacy field that is not supported anymore but cannot be dropped due to backwards compatibility.
# Consider this as being deprecated.
class SpecWorkerConfig(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    type: str | None = Field(default=None)
    document_type: str | None = Field(default=None, alias="document-type")


class SpecAgentMetadata(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    mode: SpecWorkerMode
    worker_config: SpecWorkerConfig | None = Field(default=None, alias="worker-config")
    question_groups: list[QuestionGroup] | None = Field(default=None, alias="question-groups")
    welcome_message: str | None = Field(default=None, alias="welcome-message")


class SpecSelectedTool(BaseModel):
    name: str

    def to_selected_tool_config(self) -> SelectedToolConfig:
        return SelectedToolConfig(name=self.name)


class SpecSelectedTools(BaseModel):
    tools: list[SpecSelectedTool] | None = None

    def to_selected_tools(self) -> SelectedTools:
        if self.tools is None:
            return SelectedTools(tools=[])
        return SelectedTools(tools=[SpecSelectedTool.to_selected_tool_config(tool) for tool in self.tools])


# A permissive implementation of the Agent Spec model, mimicking the Agent Package
# ingress behaviour we've had so far for Agent Package deployment.
# @TODO:
# Assess whether we should make it more strict in regards to required fields.
class SpecAgent(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    # Field order matches the expected YAML output order for serialization
    name: str
    description: str
    model: SpecAgentModel | None = None
    version: str
    # Even though spec files are strict in terms of architecture values,
    # we are loosening the validation here, so we can add and use new architectures more freely.
    architecture: str | None = None
    reasoning: SpecAgentReasoning | None = None
    runbook: str | None = None
    action_packages: list[SpecActionPackage] = Field(alias="action-packages")
    knowledge: list[SpecKnowledge] | None = None
    semantic_data_models: list[SpecSemanticDataModel] | None = Field(default=None, alias="semantic-data-models")
    mcp_servers: list[SpecMCPServer] | None = Field(default=None, alias="mcp-servers")
    docker_mcp_gateway: SpecDockerMcpGateway | None = Field(default=None, alias="docker-mcp-gateway")
    conversation_guide: str | None = Field(default=None, alias="conversation-guide")
    conversation_starter: str | None = Field(default=None, alias="conversation-starter")
    document_intelligence: SpecDocumentIntelligence | None = Field(default=None, alias="document-intelligence")
    welcome_message: str | None = Field(default=None, alias="welcome-message")
    metadata: SpecAgentMetadata | None = None
    selected_tools: SpecSelectedTools | None = Field(default=None, alias="selected-tools")
    agent_settings: dict[str, Any] | None = Field(default=None, alias="agent-settings")

    def to_yaml(self, *, exclude_none: bool = True) -> str:
        """Dump the SpecAgent model to YAML format.

        Args:
            exclude_none: Whether to exclude fields with None values from the output.
                Defaults to True.

        Returns:
            A YAML string representation of the SpecAgent model.
        """
        return _model_to_yaml(self, exclude_none=exclude_none)

    @classmethod
    def get_fields(cls) -> list[str]:
        return list(cls.model_fields.keys())


class AgentPackageSpecContents(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    spec_version: SpecVersion = Field(alias="spec-version")
    agents: list[SpecAgent]
    exclude: list[str] | None = None

    # Validate if there is only one Agent defined in the AgentSpec.
    @field_validator("agents", mode="before")
    @classmethod
    def validate_agents(cls, v: list[SpecAgent]) -> list[SpecAgent]:
        if len(v) != 1:
            raise ValueError("Agent Package supports single Agent definition only")
        return v

    def get_agent(self) -> SpecAgent:
        """Get the single agent from the spec.

        The spec is validated to contain exactly one agent definition,
        so this is guaranteed to return a valid agent.

        Returns:
            The single SpecAgent from this package spec.
        """
        return self.agents[0]


class AgentPackageSpec(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    agent_package: AgentPackageSpecContents = Field(alias="agent-package")

    def to_yaml(self, *, exclude_none: bool = True) -> str:
        """Dump the AgentSpec model to YAML format.

        Args:
            exclude_none: Whether to exclude fields with None values from the output.
                Defaults to True.

        Returns:
            A YAML string representation of the AgentPackageSpec model.
        """
        return _model_to_yaml(self, exclude_none=exclude_none)

    @classmethod
    def from_yaml(cls, data: bytes) -> "AgentPackageSpec":
        yaml = YAML(typ="safe")

        data = yaml.load(data)

        return cls.model_validate(data)


class AgentSpecGenerator:
    @classmethod
    def _get_architecture(cls, agent: Agent) -> str:
        return agent.agent_architecture.name.lower().strip()

    @classmethod
    def _get_model(cls, agent: Agent) -> SpecAgentModel:
        model = convert_platform_config_to_legacy_model(agent.platform_configs)
        return SpecAgentModel.model_validate({"name": model.get("name", ""), "provider": model.get("provider", "")})

    @classmethod
    def _get_reasoning(cls, agent: Agent) -> SpecAgentReasoning:
        # reasoning is always "disabled"
        return "disabled"

    @classmethod
    def _get_action_packages(
        cls, agent: Agent, action_package_type: SpecActionPackageType
    ) -> list[SpecActionPackage] | None:
        return [
            SpecActionPackage.model_validate(
                {
                    "name": ap.name,
                    "organization": ap.organization,
                    "version": ap.version,
                    "type": action_package_type,
                    "whitelist": ",".join(ap.allowed_actions),
                    "path": create_action_package_path(action_package_type, ap.organization, ap.name, ap.version),
                }
            )
            for ap in agent.action_packages
        ]

    @classmethod
    def _get_worker_config(cls, agent: Agent) -> dict[str, Any] | None:
        """Get worker config from agent, returning None for conversational mode."""
        if agent.mode == "conversational":
            return None

        if "worker-config" in agent.extra:
            return agent.extra["worker-config"]

        return agent.extra.get("worker_config", {})

    @classmethod
    def _get_metadata(cls, agent: Agent) -> SpecAgentMetadata:
        return SpecAgentMetadata.model_validate(
            {
                "mode": agent.mode,
                "worker_config": cls._get_worker_config(agent),
                # These fields were moved to the root level of the agent and should be set to None here.
                "welcome_message": None,
                "question_groups": None,
            }
        )

    @classmethod
    def _get_mcp_servers(cls, agent: Agent) -> list[SpecMCPServer] | None:
        return [SpecMCPServer.from_mcp_server(server) for server in agent.mcp_servers]

    @classmethod
    def _get_docker_mcp_gateway(
        cls, agent: Agent, docker_mcp_gateway: SpecDockerMcpGateway | None
    ) -> SpecDockerMcpGateway | None:
        """Check if any MCP server is a Docker MCP Gateway and return the gateway config."""
        for mcp_server in agent.mcp_servers:
            if not mcp_server:
                continue

            command = mcp_server.command
            args = mcp_server.args

            if not command or not args:
                continue

            # Check if this is a Docker MCP Gateway command: docker mcp gateway run
            if command == "docker" and len(args) > 2 and args[0] == "mcp" and args[1] == "gateway" and args[2] == "run":
                return docker_mcp_gateway

        return None

    @classmethod
    def _get_selected_tools(cls, agent: Agent) -> SpecSelectedTools | None:
        return SpecSelectedTools.model_validate(agent.selected_tools.model_dump())

    @classmethod
    def _get_agent_settings(cls, agent: Agent) -> dict[str, Any] | None:
        return agent.extra.get("agent_settings", None)

    @classmethod
    def _get_semantic_data_models(
        cls, semantic_data_models: list[SemanticDataModel] | None = None
    ) -> list[SpecSemanticDataModel] | None:
        if not semantic_data_models:
            return None

        return [SpecSemanticDataModel(name=sdm.name) for sdm in semantic_data_models]

    @classmethod
    def _generate_spec_exclude(cls, exclude: list[str] | None = None) -> list[str]:
        return exclude if exclude is not None else list(DEFAULT_AGENT_PACKAGE_EXCLUDE)

    @classmethod
    def _get_conversation_guide(cls, agent: Agent) -> str | None:
        # If there are no question groups, the conversation guide reference should not be included in the spec
        if not agent.question_groups or agent.question_groups == []:
            return None
        return AgentPackageConfig.conversation_guide_filename

    @classmethod
    def _normalize_spec_version(cls, version: str) -> SpecVersion:
        """Normalize agent version to a valid spec version.

        If the version is not a valid spec version (v2, v2.1, v3),
        default to v2.

        Args:
            version: The agent version string.

        Returns:
            A valid spec version, defaulting to "v2" if invalid.
        """
        valid_versions: tuple[SpecVersion, ...] = ("v2", "v2.1", "v3")
        if version in valid_versions:
            return version  # type: ignore[return-value]
        return DEFAULT_AGENT_PACKAGE_SPEC_VERSION

    @classmethod
    def _generate_spec_agent(
        cls,
        agent: Agent,
        semantic_data_models: list[SemanticDataModel] | None = None,
        docker_mcp_gateway: SpecDockerMcpGateway | None = None,
        action_package_type: SpecActionPackageType = "zip",
    ) -> SpecAgent:
        return SpecAgent.model_validate(
            {
                "name": agent.name,
                "description": agent.description,
                "version": agent.version,
                "architecture": cls._get_architecture(agent),
                "model": cls._get_model(agent),
                "reasoning": cls._get_reasoning(agent),
                "runbook": AgentPackageConfig.runbook_filename,
                "action-packages": cls._get_action_packages(agent, action_package_type),
                # knowledge - a legacy field that is not supported anymore but cannot be dropped due to compatibility
                "knowledge": [],
                "metadata": cls._get_metadata(agent),
                "mcp-servers": cls._get_mcp_servers(agent),
                "docker-mcp-gateway": cls._get_docker_mcp_gateway(agent, docker_mcp_gateway),
                "conversation-guide": cls._get_conversation_guide(agent),
                "conversation-starter": agent.extra.get("conversation_starter", None),
                "document-intelligence": agent.extra.get("document_intelligence", None),
                "welcome-message": agent.extra.get("welcome_message") or agent.extra.get("welcome-message", None),
                "selected-tools": cls._get_selected_tools(agent),
                "agent-settings": cls._get_agent_settings(agent),
                "semantic-data-models": cls._get_semantic_data_models(semantic_data_models),
            }
        )

    @classmethod
    def from_agent(
        cls,
        agent: Agent,
        semantic_data_models: list[SemanticDataModel] | None = None,
        docker_mcp_gateway: SpecDockerMcpGateway | None = None,
        action_package_type: SpecActionPackageType = "zip",
    ) -> AgentPackageSpec:
        """Generate AgentSpec from Agent instance.

        Args:
            agent (Agent): The Agent instance to generate the spec from.
            semantic_data_models (list[SemanticDataModel] | None): List of semantic data models to include.
            docker_mcp_gateway (SpecDockerMcpGateway | None): Docker MCP Gateway configuration.
            action_package_type (SpecActionPackageType): The type of action package ("zip" or "folder").
        Returns:
            AgentSpec: The generated AgentSpec instance.
        """
        return AgentPackageSpec.model_validate(
            {
                "agent-package": AgentPackageSpecContents.model_validate(
                    {
                        "spec-version": cls._normalize_spec_version(DEFAULT_AGENT_PACKAGE_SPEC_VERSION),
                        "agents": [
                            cls._generate_spec_agent(
                                agent, semantic_data_models, docker_mcp_gateway, action_package_type
                            )
                        ],
                        "exclude": cls._generate_spec_exclude(),
                    }
                )
            }
        )

    @classmethod
    def to_agent(
        cls,
        spec_agent: SpecAgent,
        spec_runbook: str | None = None,
        spec_question_groups: list[QuestionGroup] | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
    ) -> Agent:
        """Convert a SpecAgent to an Agent for comparison purposes.

        This creates an Agent object from a SpecAgent, using the same conversion
        logic as the package upload process but without requiring storage or HTTP context.

            Args:
                spec_agent: The agent specification from agent-spec.yaml.
            spec_runbook: Optional runbook content read from the runbook file.
            spec_question_groups: Optional list of question groups from conversation guide.
                    If not provided, falls back to metadata.question_groups from the spec.

            Returns:
            An Agent instance suitable for comparison with a deployed agent.
        """
        from datetime import UTC, datetime

        from agent_platform.core.agent import Agent
        from agent_platform.core.agent.agent_architecture import AgentArchitecture
        from agent_platform.core.runbook.runbook import Runbook
        from agent_platform.core.selected_tools import SelectedTools

        # Convert action packages
        action_packages = SpecActionPackage.to_agent_action_packages(spec_agent.action_packages)

        # Convert MCP servers
        mcp_servers = SpecMCPServer.to_mcp_server(spec_agent.mcp_servers)

        # Convert selected tools
        selected_tools = SelectedTools()
        if spec_agent.selected_tools:
            selected_tools = spec_agent.selected_tools.to_selected_tools()

        # Determine question groups (prefer provided, fall back to metadata)
        question_groups = spec_question_groups
        if question_groups is None and spec_agent.metadata and spec_agent.metadata.question_groups:
            question_groups = spec_agent.metadata.question_groups
        question_groups = question_groups or []

        # Build runbook
        runbook_text = spec_runbook or ""
        runbook_structured = Runbook(raw_text=runbook_text, content=[], updated_at=datetime.now(UTC))

        # Normalize architecture name
        architecture_name = (spec_agent.architecture or "default").lower().strip()
        if not architecture_name.startswith("agent_platform.architectures."):
            architecture_name = f"agent_platform.architectures.{architecture_name}"

        # Determine mode
        mode = "conversational"
        if spec_agent.metadata and spec_agent.metadata.mode:
            mode = spec_agent.metadata.mode

        # Build extra dict with additional fields
        extra: dict[str, Any] = {}
        if spec_agent.welcome_message:
            extra["welcome_message"] = spec_agent.welcome_message
        if spec_agent.conversation_starter:
            extra["conversation_starter"] = spec_agent.conversation_starter
        if spec_agent.agent_settings:
            extra["agent_settings"] = spec_agent.agent_settings
        if spec_agent.document_intelligence:
            extra["document_intelligence"] = spec_agent.document_intelligence
        if spec_agent.docker_mcp_gateway:
            extra["docker_mcp_gateway"] = spec_agent.docker_mcp_gateway.model_dump()

        return Agent(
            name=spec_agent.name,
            description=spec_agent.description,
            version=spec_agent.version,
            user_id=user_id or DEFAULT_AGENT_TEMP_USER_ID,
            agent_id=agent_id or DEFAULT_AGENT_TEMP_ID,
            runbook_structured=runbook_structured,
            action_packages=action_packages,
            mcp_servers=mcp_servers,
            selected_tools=selected_tools,
            question_groups=question_groups,
            agent_architecture=AgentArchitecture(name=architecture_name, version="1.0.0"),
            platform_configs=[],  # Will be excluded from comparison
            mode=mode,
            extra=extra,
        )
