import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    TypeAdapter,
    ValidationInfo,
    field_validator,
)

from agent_server_types.annotated import SerializableSecretStr
from agent_server_types.common import ConfigurationMixin
from agent_server_types.constants import AZURE_URL_PATTERN, NOT_CONFIGURED


class LLMProvider(StrEnum):
    """
    Enum for large language model providers.
    """

    OPENAI = "OpenAI"
    AZURE = "Azure"
    ANTHROPIC = "Anthropic"
    AMAZON = "Amazon"
    OLLAMA = "Ollama"
    SNOWFLAKE_CORTEX = "Snowflake Cortex AI"


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


class OllamaConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    ollama_base_url: str = Field(
        description="The Ollama base URL.", default=NOT_CONFIGURED
    )


class SnowflakeCortexConfig(ModelConfig):
    temperature: float = Field(description="The temperature.", default=0.0)
    # NOTE: pretty much all these fields may be left NOT_CONFIGURED when 
    # using token auth.
    snowflake_account: str|None = Field(description="The Snowflake account.", default=NOT_CONFIGURED)
    snowflake_host: str|None = Field(description="The Snowflake host.", default=NOT_CONFIGURED)
    snowflake_database: str|None = Field(description="The Snowflake database.", default=NOT_CONFIGURED)
    snowflake_schema: str|None = Field(description="The Snowflake schema.", default=NOT_CONFIGURED)
    snowflake_warehouse: str|None = Field(description="The Snowflake warehouse.", default=NOT_CONFIGURED)
    snowflake_role: str|None = Field(description="The Snowflake role.", default=NOT_CONFIGURED)
    snowflake_username: str|None = Field(description="The Snowflake username.", default=NOT_CONFIGURED)
    snowflake_password: SerializableSecretStr|None = Field(
        description="The Snowflake password.", default=SecretStr(NOT_CONFIGURED)
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
        default="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    )
    config: AmazonBedrockConfig = Field(description="Amazon Claude config.")


class Ollama(BaseModel):
    provider: Literal[LLMProvider.OLLAMA]
    name: str = Field(description="The name of the model.")
    config: OllamaConfig = Field(description="Ollama config.")


class SnowflakeCortex(BaseModel):
    provider: Literal[LLMProvider.SNOWFLAKE_CORTEX]
    name: str = Field(description="The name of the model.")
    config: SnowflakeCortexConfig = Field(description="Snowflake Cortex config.")


# Need this due to how LangChain works. Some objects are initialized during runtime
# and look for LLM's api key in environment variables. That breaks the app.
# Instead we'll use a dummy model for such scenarios. During the request-response cycle
# the actual model will be used.
dummy_model = OpenAIGPT(
    provider=LLMProvider.OPENAI, config=OpenAIGPTConfig(openai_api_key="dummy")
)

# TODO: If we unify models to the same base class, do we need this?
MODEL = Annotated[
    OpenAIGPT | AzureGPT | AnthropicClaude | AmazonBedrock | Ollama | SnowflakeCortex,
    Field(discriminator="provider"),
]
MODEL_ADAPTER = TypeAdapter(MODEL)
