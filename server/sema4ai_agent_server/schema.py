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


class LLMType(str, Enum):
    """
    Enum for large language model types.
    """

    GPT_35_TURBO = "GPT-3.5 Turbo"
    GPT_4_TURBO = "GPT-4 Turbo"
    GPT_4O = "GPT-4o"
    GEMINI_PRO = "Gemini Pro"
    CLAUDE_35_SONNET = "Claude 3.5 Sonnet"
    CLAUDE_3_OPUS = "Claude 3 Opus"
    CLAUDE_3_SONNET = "Claude 3 Sonnet"
    CLAUDE_3_HAIKU = "Claude 3 Haiku"
    LLAMA_3 = "Llama 3"
    UNSPECIFIED = ""


class OpenAIGPTConfig(BaseModel):
    openai_api_key: SecretStr = Field(description="The OpenAI API key.")


class AzureGPTConfig(BaseModel):
    deployment_name: str = Field(description="The Azure deployment name.")
    azure_endpoint: str = Field(description="The Azure endpoint.")
    openai_api_version: str = Field(description="The Azure API version.")
    openai_api_key: SecretStr = Field(description="The Azure API key.")


class AnthropicClaudeConfig(BaseModel):
    anthropic_api_key: SecretStr = Field(description="The Anthropic API key.")


class AmazonClaudeConfig(BaseModel):
    service_name: str = Field(
        description="The service name.", default="bedrock-runtime"
    )
    region_name: str = Field(description="The region name.")
    aws_access_key_id: SecretStr = Field(description="The AWS access key ID.")
    aws_secret_access_key: SecretStr = Field(description="The AWS secret access key.")


class GoogleGeminiConfig(BaseModel):
    vertex_ai_credentials: SecretStr = Field(
        description="The Google Vertex AI credentials."
    )


class OllamaConfig(BaseModel):
    ollama_base_url: str = Field(description="The Ollama base URL.")


class OpenAIGPT35Turbo(BaseModel):
    provider: Literal[LLMProvider.OPENAI]
    type: Literal[LLMType.GPT_35_TURBO]
    config: OpenAIGPTConfig = Field(description="OpenAI GPT config.")


class OpenAIGPT4Turbo(BaseModel):
    provider: Literal[LLMProvider.OPENAI]
    type: Literal[LLMType.GPT_4_TURBO]
    config: OpenAIGPTConfig = Field(description="OpenAI GPT config.")


class OpenAIGPT4o(BaseModel):
    provider: Literal[LLMProvider.OPENAI]
    type: Literal[LLMType.GPT_4O]
    config: OpenAIGPTConfig = Field(description="OpenAI GPT config.")


class AzureGPT(BaseModel):
    provider: Literal[LLMProvider.AZURE]
    type: Literal[LLMType.UNSPECIFIED]
    config: AzureGPTConfig = Field(description="Azure GPT config.")


class AnthropicClaude35Sonnet(BaseModel):
    provider: Literal[LLMProvider.ANTHROPIC]
    type: Literal[LLMType.CLAUDE_35_SONNET]
    config: AnthropicClaudeConfig = Field(description="Anthropic Claude config.")


class AnthropicClaude3Opus(BaseModel):
    provider: Literal[LLMProvider.ANTHROPIC]
    type: Literal[LLMType.CLAUDE_3_OPUS]
    config: AnthropicClaudeConfig = Field(description="Anthropic Claude config.")


class AnthropicClaude3Sonnet(BaseModel):
    provider: Literal[LLMProvider.ANTHROPIC]
    type: Literal[LLMType.CLAUDE_3_SONNET]
    config: AnthropicClaudeConfig = Field(description="Anthropic Claude config.")


class AnthropicClaude3Haiku(BaseModel):
    provider: Literal[LLMProvider.ANTHROPIC]
    type: Literal[LLMType.CLAUDE_3_HAIKU]
    config: AnthropicClaudeConfig = Field(description="Anthropic Claude config.")


class AmazonClaude35Sonnet(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    type: Literal[LLMType.CLAUDE_35_SONNET]
    config: AmazonClaudeConfig = Field(description="Amazon Claude config.")


class AmazonClaude3Opus(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    type: Literal[LLMType.CLAUDE_3_OPUS]
    config: AmazonClaudeConfig = Field(description="Amazon Claude config.")


class AmazonClaude3Sonnet(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    type: Literal[LLMType.CLAUDE_3_SONNET]
    config: AmazonClaudeConfig = Field(description="Amazon Claude config.")


class AmazonClaude3Haiku(BaseModel):
    provider: Literal[LLMProvider.AMAZON]
    type: Literal[LLMType.CLAUDE_3_HAIKU]
    config: AmazonClaudeConfig = Field(description="Amazon Claude config.")


class GoogleGeminiPro(BaseModel):
    provider: Literal[LLMProvider.GOOGLE]
    type: Literal[LLMType.GEMINI_PRO]
    config: GoogleGeminiConfig = Field(description="Google Gemini config.")


class OllamaLlama3(BaseModel):
    provider: Literal[LLMProvider.OLLAMA]
    type: Literal[LLMType.LLAMA_3]
    config: OllamaConfig = Field(description="Ollama config.")


MODEL = (
    OpenAIGPT35Turbo
    | OpenAIGPT4Turbo
    | OpenAIGPT4o
    | AzureGPT
    | AnthropicClaude35Sonnet
    | AnthropicClaude3Opus
    | AnthropicClaude3Sonnet
    | AnthropicClaude3Haiku
    | AmazonClaude35Sonnet
    | AmazonClaude3Opus
    | AmazonClaude3Sonnet
    | AmazonClaude3Haiku
    | GoogleGeminiPro
    | OllamaLlama3
)


class Agent(BaseModel):
    """Agent model."""

    id: str = Field(description="The ID of the agent.")
    user_id: str = Field(description="The ID of the user that owns the agent.")
    name: str = Field(description="The name of the agent.")
    config: dict = Field(description="The agent config.")
    model: MODEL = Field(description="LLM model configuration for the agent.")
    updated_at: datetime = Field(description="The last time the agent was updated.")
    public: bool = Field(description="Whether the agent is public.")
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
