from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, SecretStr


class User(BaseModel):
    user_id: str = Field(description="The ID of the user.")
    sub: str = Field(description="The sub of the user (from a JWT token).")
    created_at: datetime = Field(description="The time the user was created.")


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


class ModelConfig(BaseModel):
    temperature: float = Field(description="The temperature.", default=0.0)


class OpenAIGPTConfig(ModelConfig):
    openai_api_key: SecretStr = Field(description="The OpenAI API key.")


class AzureGPTConfig(ModelConfig):
    deployment_name: str = Field(description="The Azure deployment name.")
    azure_endpoint: str = Field(description="The Azure endpoint.")
    openai_api_version: str = Field(description="The Azure API version.")
    openai_api_key: SecretStr = Field(description="The Azure API key.")


class AnthropicClaudeConfig(ModelConfig):
    anthropic_api_key: SecretStr = Field(description="The Anthropic API key.")


class AmazonClaudeConfig(BaseModel):
    service_name: str = Field(
        description="The service name.", default="bedrock-runtime"
    )
    region_name: str = Field(description="The region name.")
    aws_access_key_id: SecretStr = Field(description="The AWS access key ID.")
    aws_secret_access_key: SecretStr = Field(description="The AWS secret access key.")


class GoogleGeminiConfig(ModelConfig):
    vertex_ai_credentials: SecretStr = Field(
        description="The Google Vertex AI credentials."
    )


class OllamaConfig(ModelConfig):
    ollama_base_url: str = Field(description="The Ollama base URL.")


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


class Agent(BaseModel):
    """Agent model."""

    id: str = Field(description="The ID of the agent.")
    user_id: str = Field(description="The ID of the user that owns the agent.")
    name: str = Field(description="The name of the agent.")
    description: str = Field(description="The description of the agent.")
    runbook: str = Field(description="The runbook for the agent.")
    config: dict = Field(description="The agent config.")
    model: MODEL = Field(description="LLM model configuration for the agent.")
    architecture: AgentArchitecture = Field(
        description="The cognitive architecture of the agent."
    )
    updated_at: datetime = Field(description="The last time the agent was updated.")
    metadata: Optional[dict] = Field(description="The agent metadata.")


class Thread(BaseModel):
    thread_id: str = Field(description="The ID of the thread.")
    user_id: str = Field(description="The ID of the user.")
    agent_id: Optional[str] = Field(description="The ID of the agent.")
    name: str = Field(description="The name of the thread.")
    updated_at: datetime = Field(description="The last time the thread was updated.")
    metadata: Optional[dict] = Field(description="The thread metadata.")


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
