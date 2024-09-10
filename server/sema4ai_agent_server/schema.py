import re
from datetime import datetime
from enum import Enum
from functools import cached_property
from typing import Annotated, Any, List, Literal, Self, Union
from uuid import UUID

from anthropic import APIError as AnthropiAPIError
from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from openai import APIError as OpenaiAPIError
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.functional_serializers import WrapSerializer
from pydantic_core import ErrorDetails
from sse_starlette import ServerSentEvent

from sema4ai_agent_server.message_types import AnyNonChunkStreamedMessage

NOT_CONFIGURED = "SEMA4AI_FIELD_NOT_CONFIGURED"
AZURE_URL_PATTERN = r"^(https?://[^/]+)/openai/deployments/([^/]+)/(chat/completions|embeddings)\?api-version=(.+)$"
DICT_ADAPTER = TypeAdapter(dict)


def ser_secret_str(
    value: SecretStr, nxt: SerializerFunctionWrapHandler, info: SerializationInfo
) -> str:
    """Serializer function which unmasks secret strings if the context's "raw"
    key is set to True."""
    if info.context is not None and info.context.get("raw", False):
        return value.get_secret_value()
    else:
        return nxt(value, info)


RAW_CONTEXT = {"raw": True}

SerializableSecretStr = Annotated[SecretStr, WrapSerializer(ser_secret_str)]

StrWithUuidInput = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, UUID) else v)
]


class User(BaseModel):
    user_id: StrWithUuidInput = Field(description="The ID of the user.")
    sub: str = Field(description="The sub of the user (from a JWT token).")
    created_at: datetime = Field(description="The time the user was created.")

    @cached_property
    def _parsed_sub(self) -> dict[str, str] | None:
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
    def cr_tenant_id(self) -> str | None:
        """Control Room Tenant ID"""
        return self._parsed_sub["tenant"]

    @property
    def cr_user_id(self) -> str | None:
        """Control Room User ID"""
        return self._parsed_sub["user"]

    @property
    def cr_system_id(self) -> str | None:
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


class ModelConfig(BaseModel, ConfigurationMixin): ...


class OpenAIGPTConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    openai_api_key: SerializableSecretStr = Field(
        description="The OpenAI API key.", default=SecretStr(NOT_CONFIGURED)
    )


class AzureGPTConfig(ModelConfig):
    model_config = ConfigDict(validate_assignment=True)

    temperature: float = Field(description="The temperature.", default=0.0)
    chat_url: str = Field(default=NOT_CONFIGURED)
    chat_openai_api_key: SerializableSecretStr = Field(
        default=SecretStr(NOT_CONFIGURED)
    )
    embeddings_url: str = Field(default=NOT_CONFIGURED)
    embeddings_openai_api_key: SerializableSecretStr = Field(
        default=SecretStr(NOT_CONFIGURED)
    )

    @field_validator("chat_url", "embeddings_url")
    @classmethod
    def validate_url(cls, v: str, info: ValidationInfo):
        """
        chat_url format: <azure_endpoint>/openai/deployments/<deployment_name>/chat/completions?api-version=<openai_api_version>
        embeddings_url format: <azure_endpoint>/openai/deployments/<deployment_name>/embeddings?api-version=<openai_api_version>
        """

        if v == NOT_CONFIGURED:
            return v
        url_type = "chat" if info.field_name == "chat_url" else "embeddings"
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


class AnthropicClaudeConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    anthropic_api_key: SerializableSecretStr = Field(
        description="The Anthropic API key.", default=SecretStr(NOT_CONFIGURED)
    )


class AmazonBedrockConfig(ModelConfig):
    service_name: Literal["bedrock-runtime"] = "bedrock-runtime"
    region_name: str = Field(description="The region name.", default="us-east-1")
    aws_access_key_id: SerializableSecretStr = Field(
        description="The AWS access key ID.", default=SecretStr(NOT_CONFIGURED)
    )
    aws_secret_access_key: SerializableSecretStr = Field(
        description="The AWS secret access key.", default=SecretStr(NOT_CONFIGURED)
    )


class GoogleGeminiConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    vertex_ai_credentials: SerializableSecretStr = Field(
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


class AmazonBedrock(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    name: str = Field(
        description="The name of the model to use.",
        default="anthropic.claude-3-5-sonnet-20240620-v1:0",
    )
    config: AmazonBedrockConfig = Field(description="Amazon Claude config.")


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

# TODO: If we unify models to the same base class, do we need this?
MODEL = Annotated[
    OpenAIGPT | AzureGPT | AnthropicClaude | AmazonBedrock | GoogleGemini | Ollama,
    Field(discriminator="provider"),
]
MODEL_ADAPTER = TypeAdapter(MODEL)


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


class AgentNotReadyIssueType(str, Enum):
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

    architecture: AgentArchitecture = Field(
        description="The cognitive architecture of the agent."
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
        if isinstance(v, (str, bytes, bytearray)):
            return MODEL_ADAPTER.validate_json(v)
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


AGENT_LIST_ADAPTER = TypeAdapter(List[Agent])


# Similar to the dummy_model, we must creat a dummy_agent to avoid breaking the app
dummy_agent = Agent(
    id="dummy",
    user_id="dummy",
    public=False,
    status=AgentStatus.READY,
    name="dummy",
    description="dummy",
    runbook="dummy",
    version="dummy",
    model=dummy_model,
    architecture=AgentArchitecture.AGENT,
    reasoning=AgentReasoning.DISABLED,
    action_packages=[],
    updated_at=datetime.now(),
    metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
)
dummy_plan_execute_agent = dummy_agent.copy(
    update={"architecture": AgentArchitecture.PLAN_EXECUTE}
)


class Thread(BaseModel):
    thread_id: StrWithUuidInput = Field(description="The ID of the thread.")
    user_id: StrWithUuidInput = Field(description="The ID of the user.")
    agent_id: StrWithUuidInput | None = Field(None, description="The ID of the agent.")
    name: str = Field(description="The name of the thread.")
    created_at: datetime = Field(description="The time the thread was updated.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Annotated[dict | None, "db_json"] = Field(
        None, description="The thread metadata."
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict | None:
        if isinstance(v, (str, bytes, bytearray)) and v != "null":
            return DICT_ADAPTER.validate_json(v)
        elif v == "null":
            return None
        return v


THREAD_LIST_ADAPTER = TypeAdapter(List[Thread])


class EmbeddingStatus(str, Enum):
    """
    Enum for embedding status.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"


# Used to avoid breaking the app as part of agent factory creation
dummy_thread = Thread(
    thread_id="dummy",
    user_id="dummy",
    agent_id="dummy",
    name="dummy",
    updated_at=datetime.now(),
    metadata={},
)


class UploadedFile(BaseModel):
    file_id: StrWithUuidInput = Field(description="The ID of the file.")
    file_path: str | None = Field(None, description="The path of the file.")
    file_ref: str = Field(description="Key for the file access.")
    file_hash: str = Field(description="The hash of the file.")
    embedded: bool = Field(description="Whether the file is embedded.")
    file_path_expiration: datetime | None = Field(
        default=None,
        description="The expiration date of the file path.",
    )
    embedding_status: EmbeddingStatus | None = Field(
        None, description="The embedding status of the file."
    )
    agent_id: StrWithUuidInput | None = Field(
        default=None,
        description="The ID of the agent that uploaded the file.",
    )
    thread_id: StrWithUuidInput | None = Field(
        default=None,
        description="The ID of the thread that uploaded the file.",
    )


UPLOADED_FILE_LIST_ADAPTER = TypeAdapter(List[UploadedFile])


class UploadFileRequest(BaseModel):
    file: UploadFile
    embedded: bool | None = Field(
        default=None,
        description="Whether the file is embedded. If None, it will be inferred "
        "from file type.",
    )


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

    id: StrWithUuidInput | None = Field(
        None, description="The ID of the chat message. This can be a random UUID."
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
    thread_id: StrWithUuidInput = Field(description="The ID of the thread.")

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


class AgentMetrics(BaseModel):
    threads_count: int = Field(description="Number of threads of the agent.")
    messages_count: int = Field(
        description="Number of messages in all threads of the agent."
    )
    files_count: int = Field(
        description="Number of files for the agent and agent threads."
    )


class StreamMetadata(BaseModel):
    """
    Metadata emitted by the agent server when streaming a chat request.
    """

    run_id: str = Field(description="The run ID.")


StreamDataType = list[AnyNonChunkStreamedMessage]
StreamDataAdapter = TypeAdapter(StreamDataType)


class StreamErrorData(BaseModel):
    """
    Error data emitted by the agent server when streaming a chat request.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status_code: int = Field(description="The status code associated with the error.")
    message: str | list[ErrorDetails] = Field(description="The error message.")
    _exception: Exception = PrivateAttr()

    @classmethod
    def from_error(cls, error: Exception) -> Self:
        """Converts the provided exception into a StreamErrorData instance."""
        # TODO: Expand on for future custom error handling for custom graphs. Future custom
        # error types should be unified across the server and include attributes related
        # to the current provider, model, and other relevant information, as well as
        # allow for control of what is provided to the client/user.
        if isinstance(
            error,
            (OpenaiAPIError, AnthropiAPIError, Boto3Error, BotoCoreError, ClientError),
        ):
            try:
                if isinstance(error, OpenaiAPIError):
                    return cls(
                        status_code=getattr(error, "status_code", 500),
                        message=f"Stream failed due to model API error: {error.message}",
                        _exception=error,
                    )
                if isinstance(error, AnthropiAPIError):
                    return cls(
                        status_code=getattr(error, "status_code", 500),
                        message=f"Stream failed due to model API error: {error.message}",
                        _exception=error,
                    )
                if isinstance(error, Boto3Error):
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
                if isinstance(error, BotoCoreError):
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
                if isinstance(error, ClientError):
                    if "Input is too long" in str(error):
                        return cls(
                            status_code=400,
                            message=f"Stream failed due to model API error: {str(error)}",
                            _exception=error,
                        )
                    return cls(
                        status_code=500,
                        message=f"Stream failed due to model API error: {str(error)}",
                        _exception=error,
                    )
            except Exception:
                # TODO: This might leak too much info
                return cls(status_code=500, message=str(error), _exception=error)
        if isinstance(error, ValidationError):
            return cls(
                status_code=500,
                message=error.errors(include_url=False),
                _exception=error,
            )
        return cls(status_code=500, message="Internal server error.", _exception=error)


class BaseStreamEvent(BaseModel):
    """
    A stream event emitted by the agent server when streaming a
    chat request.
    """

    event: Literal["metadata", "data", "error", "end"] = Field(
        description="The event type."
    )
    data: StreamMetadata | StreamDataType | StreamErrorData | None = Field(
        description="The event data."
    )

    def to_sse(self) -> ServerSentEvent:
        """
        Converts the stream event into a ServerSentEvent instance.
        """
        if self.event == "data":
            data = StreamDataAdapter.dump_json(self.data).decode()
        elif self.event != "end":
            data = self.data.model_dump_json()
        else:
            data = None
        return ServerSentEvent(data=data, event=self.event)


class StreamMetadataEvent(BaseStreamEvent):
    event: Literal["metadata"] = "metadata"
    data: StreamMetadata


class StreamDataEvent(BaseStreamEvent):
    event: Literal["data"] = "data"
    data: StreamDataType


class StreamErrorEvent(BaseStreamEvent):
    event: Literal["error"] = "error"
    data: StreamErrorData


class StreamEndEvent(BaseStreamEvent):
    event: Literal["end"] = "end"
    data: None = None


AgentStreamEvent = Annotated[
    StreamMetadataEvent | StreamDataEvent | StreamErrorEvent | StreamEndEvent,
    Field(discriminator="event"),
]
AgentStreamEventAdapter = TypeAdapter(AgentStreamEvent)
