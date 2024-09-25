import re
from datetime import datetime
from enum import Enum
from functools import cached_property
from typing import List, Literal, Optional, Union

from fastapi import UploadFile
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field, SecretStr, root_validator, validator

NOT_CONFIGURED = "SEMA4AI_FIELD_NOT_CONFIGURED"
AZURE_URL_PATTERN = r"^(https?://[^/]+)/openai/deployments/([^/]+)/(chat/completions|embeddings)\?api-version=(.+)$"


class User(BaseModel):
    user_id: str = Field(description="The ID of the user.")
    sub: str = Field(description="The sub of the user (from a JWT token).")
    created_at: datetime = Field(description="The time the user was created.")

    @cached_property
    def _parsed_sub(self) -> dict[str, Optional[str]]:
        """
        Control Room sub formats:

        tenant:<ID>:user:<ID>
        tenant:<ID>:system:<ID>
        tenant:<ID>
        """
        pattern = r"^tenant:([^:]+)(?::(?P<type>user|system):(?P<id>[^:]+))?$"
        match = re.match(pattern, self.sub)

        if not match:
            return {"tenant": None, "user": None, "system": None}

        result = {"tenant": match.group(1), "user": None, "system": None}
        if match.group("type"):
            result[match.group("type")] = match.group("id")

        return result

    @property
    def cr_tenant_id(self) -> Optional[str]:
        """Control Room Tenant ID"""
        return self._parsed_sub["tenant"]

    @property
    def cr_user_id(self) -> Optional[str]:
        """Control Room User ID"""
        return self._parsed_sub["user"]

    @property
    def cr_system_id(self) -> Optional[str]:
        """Control Room System ID"""
        return self._parsed_sub["system"]


class LLMProvider(str, Enum):
    """
    Enum for large language model providers.
    """

    OPENAI = "OpenAI"
    AZURE = "Azure"
    ANTHROPIC = "Anthropic"
    GOOGLE = "Google"
    AMAZON = "Amazon"
    OLLAMA = "Ollama"


class ConfigurationMixin:
    def is_configured(self) -> tuple[bool, list[str]]:
        fields_not_configured = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, SecretStr):
                if field_value.get_secret_value() == NOT_CONFIGURED:
                    fields_not_configured.append(field_name)
            elif field_value == NOT_CONFIGURED:
                fields_not_configured.append(field_name)

        return len(fields_not_configured) == 0, fields_not_configured


class ModelConfig(BaseModel, ConfigurationMixin):
    ...


class OpenAIGPTConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    openai_api_key: SecretStr = Field(
        description="The OpenAI API key.", default=SecretStr(NOT_CONFIGURED)
    )


class AzureGPTConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    chat_url: str = Field(default=NOT_CONFIGURED)
    chat_openai_api_key: SecretStr = Field(default=SecretStr(NOT_CONFIGURED))
    embeddings_url: str = Field(default=NOT_CONFIGURED)
    embeddings_openai_api_key: SecretStr = Field(default=SecretStr(NOT_CONFIGURED))

    @validator("chat_url", "embeddings_url")
    def validate_url(cls, v, field):
        """
        chat_url format: <azure_endpoint>/openai/deployments/<deployment_name>/chat/completions?api-version=<openai_api_version>
        embeddings_url format: <azure_endpoint>/openai/deployments/<deployment_name>/embeddings?api-version=<openai_api_version>
        """

        if v == NOT_CONFIGURED:
            return v
        url_type = "chat" if field.name == "chat_url" else "embeddings"
        match = re.match(AZURE_URL_PATTERN, v)
        if not match:
            raise ValueError(f"Invalid {url_type} URL format")

        endpoint_type = match.group(3)
        if url_type == "chat" and endpoint_type != "chat/completions":
            raise ValueError("Chat URL must end with 'chat/completions'")
        if url_type == "embeddings" and endpoint_type != "embeddings":
            raise ValueError("Embeddings URL must end with 'embeddings'")

        return v

    @property
    def chat_deployment_name(self):
        return self._get_url_component(self.chat_url, 2)

    @property
    def chat_azure_endpoint(self):
        return self._get_url_component(self.chat_url, 1)

    @property
    def chat_openai_api_version(self):
        return self._get_url_component(self.chat_url, 4)

    @property
    def embeddings_deployment_name(self):
        return self._get_url_component(self.embeddings_url, 2)

    @property
    def embeddings_azure_endpoint(self):
        return self._get_url_component(self.embeddings_url, 1)

    @property
    def embeddings_openai_api_version(self):
        return self._get_url_component(self.embeddings_url, 4)

    def _get_url_component(self, url, group):
        if url == NOT_CONFIGURED:
            return NOT_CONFIGURED
        match = re.match(AZURE_URL_PATTERN, url)
        return match.group(group) if match else NOT_CONFIGURED

    class Config:
        validate_assignment = True


class AnthropicClaudeConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    anthropic_api_key: SecretStr = Field(
        description="The Anthropic API key.", default=SecretStr(NOT_CONFIGURED)
    )


class AmazonClaudeConfig(ModelConfig):
    service_name: str = Field(description="The service name.", default=NOT_CONFIGURED)
    region_name: str = Field(description="The region name.", default=NOT_CONFIGURED)
    aws_access_key_id: SecretStr = Field(
        description="The AWS access key ID.", default=SecretStr(NOT_CONFIGURED)
    )
    aws_secret_access_key: SecretStr = Field(
        description="The AWS secret access key.", default=SecretStr(NOT_CONFIGURED)
    )


class GoogleGeminiConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    vertex_ai_credentials: SecretStr = Field(
        description="The Google Vertex AI credentials.",
        default=SecretStr(NOT_CONFIGURED),
    )


class OllamaConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    ollama_base_url: str = Field(
        description="The Ollama base URL.", default=NOT_CONFIGURED
    )


class OpenAIGPT(BaseModel):
    provider: Literal[LLMProvider.OPENAI]
    name: str = Field(description="The name of the model.", default="gpt-3.5-turbo")
    config: OpenAIGPTConfig = Field(description="OpenAI GPT config.")


class AzureGPT(BaseModel):
    provider: Literal[LLMProvider.AZURE]
    config: AzureGPTConfig = Field(description="Azure GPT config.")


class AnthropicClaude(BaseModel):
    provider: Literal[LLMProvider.ANTHROPIC]
    name: str = Field(
        description="The name of the model.", default="claude-3-5-sonnet-20240620"
    )
    config: AnthropicClaudeConfig = Field(description="Anthropic Claude config.")


class AmazonClaude(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    name: str = Field(
        description="The name of the model.",
        default="anthropic.claude-3-5-sonnet-20240620-v1:0",
    )
    config: AmazonClaudeConfig = Field(description="Amazon Claude config.")


class GoogleGemini(BaseModel):
    provider: Literal[LLMProvider.GOOGLE]
    name: str = Field(description="The name of the model.", default="gemini-pro")
    config: GoogleGeminiConfig = Field(description="Google Gemini config.")


class Ollama(BaseModel):
    provider: Literal[LLMProvider.OLLAMA]
    name: str = Field(description="The name of the model.")
    config: OllamaConfig = Field(description="Ollama config.")


# Need this due to how LangChain works. Some objects are initialized during runtime
# and look for LLM's api key in environment variables. That breaks the app.
# Instead we'll use a dummy model for such scenarios. During the request-response cycle
# the actual model will be used.
dummy_model = OpenAIGPT(
    provider=LLMProvider.OPENAI, config=OpenAIGPTConfig(openai_api_key="dummy")
)

MODEL = OpenAIGPT | AzureGPT | AnthropicClaude | AmazonClaude | GoogleGemini | Ollama


class AgentArchitecture(str, Enum):
    """
    Enum for agent cognitive architecture.
    """

    AGENT = "agent"
    PLAN_EXECUTE = "plan_execute"
    MULTI_AGENT_HIERARCHICAL_PLANNING = "multi_agent_hierarchical_planning"


class AgentReasoning(str, Enum):
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
    api_key: SecretStr = Field(
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
    additional_headers: dict = Field(
        description="Additional headers to be sent with the request to the action server.",
        default_factory=dict,
    )


class AgentNotReadyIssueType(str, Enum):
    MODEL_NOT_CONFIGURED = "model_not_configured"
    ACTION_SERVER_NOT_CONFIGURED = "action_server_not_configured"
    EMBEDDING_FILES_PENDING = "embedding_files_pending"
    EMBEDDING_FILES_IN_PROGRESS = "embedding_files_in_progress"
    EMBEDDING_FILES_FAILED = "embedding_files_failed"


class AgentNotReadyIssue(BaseModel):
    type: AgentNotReadyIssueType


class ModelNotConfigured(AgentNotReadyIssue):
    type: Literal[
        AgentNotReadyIssueType.MODEL_NOT_CONFIGURED
    ] = AgentNotReadyIssueType.MODEL_NOT_CONFIGURED
    fields: list[str]


class ActionServerNotConfigured(AgentNotReadyIssue):
    type: Literal[
        AgentNotReadyIssueType.ACTION_SERVER_NOT_CONFIGURED
    ] = AgentNotReadyIssueType.ACTION_SERVER_NOT_CONFIGURED
    action_package_name: str
    fields: list[str]


class EmbeddingFilePending(AgentNotReadyIssue):
    type: Literal[
        AgentNotReadyIssueType.EMBEDDING_FILES_PENDING
    ] = AgentNotReadyIssueType.EMBEDDING_FILES_PENDING
    file_ref: str


class EmbeddingFileInProgress(AgentNotReadyIssue):
    type: Literal[
        AgentNotReadyIssueType.EMBEDDING_FILES_IN_PROGRESS
    ] = AgentNotReadyIssueType.EMBEDDING_FILES_IN_PROGRESS
    file_ref: str


class EmbeddingFileFailed(AgentNotReadyIssue):
    type: Literal[
        AgentNotReadyIssueType.EMBEDDING_FILES_FAILED
    ] = AgentNotReadyIssueType.EMBEDDING_FILES_FAILED
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


class AgentMode(str, Enum):
    """
    Enum for agent mode.
    """

    CONVERSATIONAL = "conversational"
    WORKER = "worker"


class WorkerType(str, Enum):
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


class AgentMetadata(BaseModel):
    """
    Metadata for the agent.
    """

    mode: AgentMode = Field(description="The mode of the agent.")
    worker_config: Optional[WorkerConfig] = Field(
        description="Worker configuration, if in worker mode."
    )
    welcome_message: Optional[str] = Field(description="Welcome message for the agent.")
    question_groups: list[QuestionGroup] = Field(
        description="Question groups for the agent.", default_factory=list
    )

    @root_validator
    def validate_worker_config(cls, values):
        mode = values.get("mode")
        worker_config = values.get("worker_config")

        if mode == AgentMode.WORKER and worker_config is None:
            raise ValueError("worker_config must be set when mode is 'worker'")

        if mode == AgentMode.CONVERSATIONAL and worker_config is not None:
            raise ValueError(
                "worker_config should not be set when mode is 'conversational'"
            )

        return values


class BaseAgent(BaseModel):
    """
    Agent model that always masks sensitive information.

    Both .dict() and .json() will contain masked values for sensitive fields.
    Ensures that logs and traces do not contain sensitive information.
    """

    id: str = Field(description="The ID of the agent.")
    user_id: str = Field(description="The ID of the user that owns the agent.")
    public: bool = Field(description="Whether the agent is public.")
    name: str = Field(description="The name of the agent.")
    description: str = Field(description="The description of the agent.")
    runbook: SecretStr = Field(description="The runbook for the agent.")
    version: str = Field(description="The version of the agent.")
    model: MODEL = Field(description="LLM model configuration for the agent.")
    architecture: AgentArchitecture = Field(
        description="The cognitive architecture of the agent."
    )
    reasoning: AgentReasoning = Field(description="The reasoning setting of the agent.")
    action_packages: list[ActionPackage] = Field(
        description="The action packages for the agent."
    )
    updated_at: datetime = Field(description="The last time the agent was updated.")
    metadata: AgentMetadata = Field(description="The agent metadata.")


class RawAgent(BaseAgent):
    """
    Agent model that does not mask sensitive information in its JSON representation.

    Logs and traces will still not contain sensitive information but clients can
    view raw agent data.
    """

    class Config:
        # Ensure that SecretStr is not masked
        json_encoders = {SecretStr: lambda v: v.get_secret_value() if v else None}


class Agent(BaseAgent):
    def raw(self) -> RawAgent:
        return RawAgent(**self.dict())


class Thread(BaseModel):
    thread_id: str = Field(description="The ID of the thread.")
    user_id: str = Field(description="The ID of the user.")
    agent_id: Optional[str] = Field(description="The ID of the agent.")
    name: str = Field(description="The name of the thread.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Optional[dict] = Field(description="The thread metadata.")


class EmbeddingStatus(str, Enum):
    """
    Enum for embedding status.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"


class UploadedFile(BaseModel):
    file_id: str
    """The ID of the file."""
    file_path: Optional[str]
    """The path of the file."""
    file_ref: str
    """Key for the file access."""
    file_hash: str
    """The hash of the file."""
    embedded: bool
    """Whether the file is embedded."""
    file_path_expiration: Optional[datetime] = None
    embedding_status: Optional[EmbeddingStatus]
    """The embedding status of the file."""
    file_path_expiration: Optional[datetime] = None
    agent_id: Optional[str] = None
    """The ID of the agent that uploaded the file."""
    thread_id: Optional[str] = None
    """The ID of the thread that uploaded the file."""


class UploadFileRequest(BaseModel):
    file: UploadFile
    embedded: Optional[bool] = None
    """If None, it will be inferred from file type."""


class ChatRole(str, Enum):
    """
    Enum for chat participant types.
    """

    AI = "ai"
    HUMAN = "human"
    SYSTEM = "system"
    ACTION = "tool"


class ChatMessage(BaseModel):
    """
    Represents a chat message in a thread.
    A chat message can be from the ai, human, system, or action.
    """

    id: Optional[str] = Field(
        description="The ID of the chat message. This can be a random UUID."
    )
    type: ChatRole = Field(description="The role of the chat message.")
    content: str = Field(description="The message.")
    example: bool = Field(
        description="Whether the message is an example.", default=False
    )


class ChatRequest(BaseModel):
    """
    A request to chat with an Agent Thread.
    """

    input: List[ChatMessage] = Field(description="The messages to send to the agent.")
    thread_id: str = Field(description="The ID of the thread.")

    def get_langchain_messages(self):
        """
        Get the messages in LangChain format.
        """
        messages = []
        for message in self.input:
            match message.type:
                case ChatRole.HUMAN:
                    messages.append(
                        HumanMessage(content=message.content, id=message.id)
                    )
                case ChatRole.AI:
                    messages.append(AIMessage(content=message.content, id=message.id))
                case ChatRole.SYSTEM:
                    messages.append(
                        SystemMessage(content=message.content, id=message.id)
                    )
                case ChatRole.ACTION:
                    messages.append(ToolMessage(content=message.content, id=message.id))
                case _:
                    pass
        return messages
