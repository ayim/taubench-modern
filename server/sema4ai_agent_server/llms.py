from typing import Callable, Optional

import boto3
import structlog
import tiktoken
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrockConverse
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel

from sema4ai_agent_server.schema import MODEL, LLMProvider

logger = structlog.get_logger(__name__)

DEFAULT_MAX_RETRIES = 5
CONTEXT_WINDOW_SIZES = {
    LLMProvider.OPENAI: {
        "gpt-3.5-turbo": 16385,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
    },
    LLMProvider.AMAZON: {
        "anthropic.claude-3-haiku-20240307-v1:0": 200000,
        "anthropic.claude-3-sonnet-20240229-v1:0": 200000,
        "anthropic.claude-3-opus-20240229-v1:0": 200000,
        "anthropic.claude-3-5-sonnet-20240620-v1:0": 200000,
    },
}


class ContextStats(BaseModel):
    context_window_size: Optional[int]
    tokens_per_message: dict[str, int]


class ContextSummary(BaseModel):
    context_window_size: Optional[int]
    total_tokens: int


def get_context_summary(stats: ContextStats) -> ContextSummary:
    return ContextSummary(
        context_window_size=stats.context_window_size,
        total_tokens=sum(stats.tokens_per_message.values()),
    )


def get_context_stats(model: MODEL, thread_state: dict) -> ContextStats:
    if model.provider not in (
        LLMProvider.OPENAI,
        LLMProvider.AZURE,
        LLMProvider.AMAZON,
    ):
        raise ValueError(f"Unsupported model provider: {model.provider}")
    context_window_size = _get_context_window_size(model)
    messages = thread_state.get("values", {}).get("messages", [])
    return ContextStats(
        context_window_size=context_window_size,
        tokens_per_message=_count_tokens_per_message(model, messages),
    )


def _get_context_window_size(model: MODEL) -> Optional[int]:
    match model.provider:
        case LLMProvider.OPENAI | LLMProvider.AMAZON:
            return CONTEXT_WINDOW_SIZES.get(model.provider, {}).get(model.name)
        case LLMProvider.AZURE:
            # We don't know which model is used so we return the most common size for GPTs
            return 128000
        case _:
            return None


def _token_counter(model: MODEL) -> Callable[[str], int]:
    match model.provider:
        case LLMProvider.OPENAI:
            try:
                # Raise KeyError if the model name is not recognized
                encoding = tiktoken.encoding_for_model(model.name)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
            return lambda s: len(encoding.encode(s))

        case LLMProvider.AZURE:
            encoding = tiktoken.get_encoding("cl100k_base")
            return lambda s: len(encoding.encode(s))

        case _:
            return lambda s: len(s) // 4


def _count_tokens_per_message(
    model: MODEL, messages: list[BaseMessage]
) -> dict[str, int]:
    counter = _token_counter(model)
    return {m.id: counter(m.content) for m in messages}


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
            return ChatBedrockConverse(model=model.name, client=client)
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
