from typing import Optional

import boto3
import structlog
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import BedrockChat
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from sema4ai_agent_server.schema import MODEL, LLMProvider

logger = structlog.get_logger(__name__)

DEFAULT_MAX_RETRIES = 5


def get_chat_model(model: MODEL) -> Optional[BaseChatModel]:
    match model.provider:
        case LLMProvider.OPENAI:
            return ChatOpenAI(
                model_name=model.name,
                openai_api_key=model.config.openai_api_key.get_secret_value(),
                temperature=model.config.temperature,
                max_retries=DEFAULT_MAX_RETRIES,
            )
        case LLMProvider.AZURE:
            return AzureChatOpenAI(
                deployment_name=model.config.chat_deployment_name,
                azure_endpoint=model.config.chat_azure_endpoint,
                openai_api_version=model.config.chat_openai_api_version,
                openai_api_key=model.config.chat_openai_api_key.get_secret_value(),
                temperature=model.config.temperature,
                max_retries=DEFAULT_MAX_RETRIES,
            )
        case LLMProvider.ANTHROPIC:
            return ChatAnthropic(
                model=model.name,
                anthropic_api_key=model.config.anthropic_api_key.get_secret_value(),
                max_tokens=2000,
                temperature=model.config.temperature,
                max_retries=DEFAULT_MAX_RETRIES,
            )
        case LLMProvider.AMAZON:
            client = boto3.client(
                model.config.service_name,
                region_name=model.config.region_name,
                aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
                aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
            )
            return BedrockChat(model_id=model.name, client=client)
        case LLMProvider.GOOGLE:
            return ChatVertexAI(
                model_name=model.name,
                convert_system_message_to_human=True,
                streaming=True,
                credentials=model.config.vertex_ai_credentials.get_secret_value(),
                temperature=model.config.temperature,
                max_retries=DEFAULT_MAX_RETRIES,
            )
        case LLMProvider.OLLAMA:
            return ChatOllama(
                model=model.name,
                base_url=model.config.ollama_base_url,
                temperature=model.config.temperature,
            )
        case _:
            return None
