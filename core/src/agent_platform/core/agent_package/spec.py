from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from ruamel.yaml import YAML

from agent_platform.core.mcp.mcp_types import MCPUnionOfVariableTypes
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools

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


class SpecKnowledge(BaseModel):
    name: str
    embedded: bool
    digest: str | None = None


class SpecSemanticDataModel(BaseModel):
    name: str


class SpecMCPServer(BaseModel):
    name: str
    transport: SpecMCPTransport | None = None
    description: str | None = None
    url: str | None = None
    headers: dict[str, MCPUnionOfVariableTypes] | None = None
    command_line: list[str] | None = Field(default=None, alias="command-line")
    env: dict[str, MCPUnionOfVariableTypes] | None = None
    cwd: str | None = None
    force_serial_tool_calls: bool | None = Field(default=False, alias="force-serial-tool-calls")


class SpecDockerMcpGateway(BaseModel):
    catalog: str | None = None
    servers: dict[str, dict[str, Any]]


class SpecAgentMetadata(BaseModel):
    mode: SpecWorkerMode


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


class SpecAgentPackage(BaseModel):
    spec_version: SpecVersion = Field(alias="spec-version")
    exclude: list[str] | None = None
    agents: list[SpecAgent]

    # Validate if there is only one Agent defined in the AgentSpec.
    @field_validator("agents", mode="before")
    @classmethod
    def validate_agents(cls, v: list[SpecAgent]) -> list[SpecAgent]:
        if len(v) != 1:
            raise ValueError("Agent Package supports single Agent definition only")
        return v


class AgentSpec(BaseModel):
    agent_package: SpecAgentPackage = Field(alias="agent-package")

    @classmethod
    def from_yaml(cls, data: bytes) -> "AgentSpec":
        yaml = YAML(typ="safe")

        data = yaml.load(data)

        return cls.model_validate(data)
