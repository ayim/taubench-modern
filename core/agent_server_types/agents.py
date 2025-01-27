import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, List, Literal, Self, Union

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from agent_server_types.annotated import SerializableSecretStr, StrWithUuidInput
from agent_server_types.common import ConfigurationMixin
from agent_server_types.constants import (
    DEFAULT_ARCHITECTURE,
    NOT_CONFIGURED,
)
from agent_server_types.models import (
    MODEL,
    MODEL_ADAPTER,
    AmazonBedrock,
    AnthropicClaude,
    AzureGPT,
    OpenAIGPT,
    dummy_model,
)


class AgentReasoning(StrEnum):
    """
    Enum for agent reasoning.
    """

    DISABLED = "disabled"
    ENABLED = "enabled"
    VERBOSE = "verbose"


class ActionPackage(BaseModel, ConfigurationMixin):
    """
    Action Package Definition.
    """

    name: str = Field(description="The name of the action package.")
    organization: str = Field(description="The organization of the action package.")
    version: str = Field(description="The version of the action package.")
    url: str = Field(
        description="URL of the action server that hosts the action package.",
        default=NOT_CONFIGURED,
    )
    api_key: SerializableSecretStr = Field(
        description="API Key of the action server that hosts the action package.",
        default=SecretStr(NOT_CONFIGURED),
    )
    whitelist: str = Field(
        description=(
            "Whitelist of actions (comma separated) that are accepted in the action package. "
            "An empty string value for whitelist implies usage of all actions."
        ),
        default="",
    )


ACTION_PKG_LIST_ADAPTER = TypeAdapter(List[ActionPackage])


class AgentNotReadyIssueType(StrEnum):
    MODEL_NOT_CONFIGURED = "model_not_configured"
    ACTION_SERVER_NOT_CONFIGURED = "action_server_not_configured"
    EMBEDDING_FILES_PENDING = "embedding_files_pending"
    EMBEDDING_FILES_IN_PROGRESS = "embedding_files_in_progress"
    EMBEDDING_FILES_FAILED = "embedding_files_failed"


class AgentNotReadyIssue(BaseModel):
    type: AgentNotReadyIssueType


class ModelNotConfigured(AgentNotReadyIssue):
    type: Literal[AgentNotReadyIssueType.MODEL_NOT_CONFIGURED] = (
        AgentNotReadyIssueType.MODEL_NOT_CONFIGURED
    )
    fields: list[str]


class ActionServerNotConfigured(AgentNotReadyIssue):
    type: Literal[AgentNotReadyIssueType.ACTION_SERVER_NOT_CONFIGURED] = (
        AgentNotReadyIssueType.ACTION_SERVER_NOT_CONFIGURED
    )
    action_package_name: str
    fields: list[str]


class EmbeddingFilePending(AgentNotReadyIssue):
    type: Literal[AgentNotReadyIssueType.EMBEDDING_FILES_PENDING] = (
        AgentNotReadyIssueType.EMBEDDING_FILES_PENDING
    )
    file_ref: str


class EmbeddingFileInProgress(AgentNotReadyIssue):
    type: Literal[AgentNotReadyIssueType.EMBEDDING_FILES_IN_PROGRESS] = (
        AgentNotReadyIssueType.EMBEDDING_FILES_IN_PROGRESS
    )
    file_ref: str


class EmbeddingFileFailed(AgentNotReadyIssue):
    type: Literal[AgentNotReadyIssueType.EMBEDDING_FILES_FAILED] = (
        AgentNotReadyIssueType.EMBEDDING_FILES_FAILED
    )
    file_ref: str


AgentNotReadyIssues = Union[
    ModelNotConfigured,
    ActionServerNotConfigured,
    EmbeddingFilePending,
    EmbeddingFileInProgress,
    EmbeddingFileFailed,
]


class AgentStatus(BaseModel):
    ready: bool
    issues: list[AgentNotReadyIssues]


class AgentMode(StrEnum):
    """
    Enum for agent mode.
    """

    CONVERSATIONAL = "conversational"
    WORKER = "worker"


class WorkerType(StrEnum):
    """
    Enum for worker type.
    """

    DOCUMENT_INTELLIGENCE = "Document Intelligence"


class WorkerConfig(BaseModel):
    """
    Worker configuration for the agent.
    """

    type: WorkerType = Field(description="The type of worker.")
    document_type: str = Field(description="The type of document.")


class QuestionGroup(BaseModel):
    title: str = Field(description="The title of the question group.")
    questions: list[str] = Field(description="The questions in the group.")


class LangsmithCredentials(BaseModel):
    """
    Langsmith credentials for the agent.
    """

    api_key: SerializableSecretStr = Field(
        ..., description="The API key for hosted Langsmith instance."
    )
    api_url: str = Field(..., description="The API URL for hosted Langsmith instance.")
    project_name: str = Field(..., description="The name of the Langsmith project.")


class AgentAdvancedConfig(BaseModel):
    """
    Advanced configuration options for the agent.
    """

    architecture: str = Field(
        description="The agent's architecture.",
    )
    reasoning: AgentReasoning = Field(description="The reasoning setting of the agent.")
    recursion_limit: int | None = Field(
        None,
        description="The maximum number of node steps allowed before the agent "
        "automatically terminates. Defaults to 100.",
    )
    langsmith: LangsmithCredentials | None = Field(
        None, description="The Langsmith credentials for the agent."
    )

    @model_validator(mode="after")
    def validate_recursion_limit(self) -> Self:
        # Default must be set via validation or the agent-server-interface will
        # set this field as required instead of allow it to be optional.
        if self.recursion_limit is None:
            self.recursion_limit = 100
        if self.recursion_limit is not None and self.recursion_limit < 0:
            raise ValueError("recursion_limit must be greater than or equal to 0")

        return self


class AgentMetadata(BaseModel):
    """
    Metadata for the agent.
    """

    mode: AgentMode = Field(description="The mode of the agent.")
    worker_config: WorkerConfig | None = Field(
        None, description="Worker configuration, if in worker mode."
    )
    welcome_message: str | None = Field(
        None, description="Welcome message for the agent."
    )
    question_groups: list[QuestionGroup] = Field(
        description="Question groups for the agent.", default_factory=list
    )

    @model_validator(mode="after")
    def validate_worker_config(self) -> Self:
        if self.mode == AgentMode.WORKER and self.worker_config is None:
            raise ValueError("worker_config must be set when mode is 'worker'")

        if self.mode == AgentMode.CONVERSATIONAL and self.worker_config is not None:
            raise ValueError(
                "worker_config should not be set when mode is 'conversational'"
            )

        return self


class AgentPayload(BaseModel):
    """Payload for creating an agent."""

    public: bool = Field(False, description="Whether the agent is public.")
    name: str = Field(..., description="The name of the agent.")
    description: str = Field(..., description="The description of the agent.")
    runbook: SerializableSecretStr = Field(
        ..., description="The runbook for the agent."
    )
    version: str = Field(..., description="The version of the agent.")
    model: Annotated[MODEL, "db_json"] = Field(
        ..., description="LLM model configuration for the agent."
    )
    advanced_config: Annotated[AgentAdvancedConfig, "db_json"] = Field(
        description="Advanced configuration options for the agent."
    )
    action_packages: Annotated[list[ActionPackage], "db_json"] = Field(
        description="The action packages for the agent."
    )
    metadata: Annotated[AgentMetadata, "db_json"] = Field(
        description="The agent metadata."
    )

    @field_validator("model", mode="before")
    @classmethod
    def validate_model_field(cls, v: Any) -> MODEL:
        if isinstance(v, (str, bytes, bytearray)) and v != "null":
            return MODEL_ADAPTER.validate_json(v)
        elif v == "null":
            raise ValueError("Model configuration cannot be null")
        return v

    @field_validator("action_packages", mode="before")
    @classmethod
    def validate_action_packages(cls, v: Any) -> list[ActionPackage]:
        if isinstance(v, (str, bytes, bytearray)):
            return ACTION_PKG_LIST_ADAPTER.validate_json(v)
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> AgentMetadata:
        if isinstance(v, (str, bytes, bytearray)):
            return AgentMetadata.model_validate_json(v)
        return v

    @field_validator("advanced_config", mode="before")
    @classmethod
    def validate_advanced_config(cls, v: Any) -> AgentAdvancedConfig:
        if isinstance(v, (str, bytes, bytearray)):
            return AgentAdvancedConfig.model_validate_json(v)
        return v

    @model_validator(mode="after")
    def translate_old_architecture(self) -> Self:
        """Translate old architecture names to new architecture names."""
        # TODO: TECH DEBT - Remove this function after all agents are updated to use the new architecture names.
        if self.advanced_config.architecture == "agent":
            if isinstance(self.model, (AnthropicClaude, AmazonBedrock)):
                self.advanced_config.architecture = "agent_architecture_claude_tools"
            else:
                self.advanced_config.architecture = "agent_architecture_default"
        elif self.advanced_config.architecture == "plan_execute":
            self.advanced_config.architecture = "agent_architecture_plan_execute"
        return self

    def to_agent(self, user_id: str) -> "Agent":
        """Generates a temp agent object that can be used to call the LLM API."""
        return Agent(
            id="temp",
            user_id=user_id,
            public=self.public,
            name=self.name,
            description=self.description,
            runbook=self.runbook,
            version=self.version,
            model=self.model,
            advanced_config=self.advanced_config,
            action_packages=self.action_packages,
            updated_at=datetime.now(),
            created_at=datetime.now(),
            metadata=self.metadata,
        )


class Agent(AgentPayload):
    """
    Agent model that masks sensitive information unless serialized with special
    context.

    SecretStr fields will be masked during serialization unless a serialization
    context of "raw" is provided when dumping the model (works with either
    model_dump or model_dump_json).
    """

    id: StrWithUuidInput = Field(description="The ID of the agent.")
    user_id: StrWithUuidInput = Field(
        description="The ID of the user that owns the agent."
    )
    updated_at: datetime = Field(description="The last time the agent was updated.")
    created_at: datetime = Field(description="The time the agent was created.")


class AgentMetrics(BaseModel):
    threads_count: int = Field(description="Number of threads of the agent.")
    messages_count: int = Field(
        description="Number of messages in all threads of the agent."
    )
    files_count: int = Field(
        description="Number of files for the agent and agent threads."
    )


AGENT_LIST_ADAPTER = TypeAdapter(List[Agent])


# Similar to the dummy_model, we must creat a dummy_agent to avoid breaking the app
dummy_agent = Agent(
    id="dummy",
    user_id="dummy",
    public=False,
    name="dummy",
    description="dummy",
    runbook="dummy",
    version="dummy",
    model=dummy_model,
    advanced_config=AgentAdvancedConfig(
        architecture=DEFAULT_ARCHITECTURE,
        reasoning=AgentReasoning.DISABLED,
    ),
    action_packages=[],
    updated_at=datetime.now(),
    metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
    created_at=datetime.now(),
)


class Memory(BaseModel):
    """Memory for the agent."""

    agent_id: str = Field(description="The ID of the agent.")
    runbook_sections: None | Annotated[dict[str, str], "db_json"] = Field(
        description="The runbook sections for the agent."
    )

    @field_validator("runbook_sections", mode="before")
    @classmethod
    def validate_runbook_sections(cls, v: Any) -> dict[str, str]:
        if isinstance(v, (str, bytes, bytearray)):
            return json.loads(v)
        return v
