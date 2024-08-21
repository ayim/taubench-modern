from typing import Optional

import boto3
import structlog
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import BedrockChat
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from sema4ai_agent_server.schema import (
    MODEL,
    AmazonClaude3Haiku,
    AmazonClaude3Opus,
    AmazonClaude3Sonnet,
    AmazonClaude35Sonnet,
    AnthropicClaude3Haiku,
    AnthropicClaude3Opus,
    AnthropicClaude3Sonnet,
    AnthropicClaude35Sonnet,
    AzureGPT,
    GoogleGeminiPro,
    OllamaLlama3,
    OpenAIGPT4o,
    OpenAIGPT4Turbo,
    OpenAIGPT35Turbo,
)

logger = structlog.get_logger(__name__)


def get_chat_model(model: MODEL) -> Optional[BaseChatModel]:
    if isinstance(model, OpenAIGPT35Turbo):
        return ChatOpenAI(
            model_name="gpt-3.5-turbo",
            openai_api_key=model.config.openai_api_key.get_secret_value(),
            temperature=0,
        )
    elif isinstance(model, OpenAIGPT4Turbo):
        return ChatOpenAI(
            model_name="gpt-4-turbo",
            openai_api_key=model.config.openai_api_key.get_secret_value(),
            temperature=0,
        )
    elif isinstance(model, OpenAIGPT4o):
        return ChatOpenAI(
            model_name="gpt-4o",
            openai_api_key=model.config.openai_api_key.get_secret_value(),
            temperature=0,
        )
    elif isinstance(model, AzureGPT):
        return AzureChatOpenAI(
            deployment_name=model.config.deployment_name,
            azure_endpoint=model.config.azure_endpoint,
            openai_api_version=model.config.openai_api_version,
            openai_api_key=model.config.openai_api_key.get_secret_value(),
            temperature=0,
        )
    elif isinstance(model, AnthropicClaude35Sonnet):
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            anthropic_api_key=model.config.anthropic_api_key.get_secret_value(),
            max_tokens=2000,
            temperature=0,
        )
    elif isinstance(model, AnthropicClaude3Opus):
        return ChatAnthropic(
            model="claude-3-opus-20240229",
            anthropic_api_key=model.config.anthropic_api_key.get_secret_value(),
            max_tokens=2000,
            temperature=0,
        )
    elif isinstance(model, AnthropicClaude3Sonnet):
        return ChatAnthropic(
            model="claude-3-sonnet-20240229",
            anthropic_api_key=model.config.anthropic_api_key.get_secret_value(),
            max_tokens=2000,
            temperature=0,
        )
    elif isinstance(model, AnthropicClaude3Haiku):
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            anthropic_api_key=model.config.anthropic_api_key.get_secret_value(),
            max_tokens=2000,
            temperature=0,
        )
    elif isinstance(model, AmazonClaude35Sonnet):
        client = boto3.client(
            model.config.service_name,
            region_name=model.config.region_name,
            aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
        )
        return BedrockChat(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", client=client
        )
    elif isinstance(model, AmazonClaude3Opus):
        client = boto3.client(
            model.config.service_name,
            region_name=model.config.region_name,
            aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
        )
        return BedrockChat(
            model_id="anthropic.claude-3-opus-20240229-v1:0", client=client
        )
    elif isinstance(model, AmazonClaude3Sonnet):
        client = boto3.client(
            model.config.service_name,
            region_name=model.config.region_name,
            aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
        )
        return BedrockChat(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0", client=client
        )
    elif isinstance(model, AmazonClaude3Haiku):
        client = boto3.client(
            model.config.service_name,
            region_name=model.config.region_name,
            aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
        )
        return BedrockChat(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", client=client
        )
    elif isinstance(model, GoogleGeminiPro):
        return ChatVertexAI(
            model_name="gemini-pro",
            convert_system_message_to_human=True,
            streaming=True,
            credentials=model.config.vertex_ai_credentials.get_secret_value(),
        )
    elif isinstance(model, OllamaLlama3):
        return ChatOllama(
            model="llama3",
            base_url=model.config.ollama_base_url,
        )
    return None
