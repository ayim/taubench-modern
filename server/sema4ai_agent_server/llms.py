from typing import Callable

import structlog
import tiktoken
from agent_server_types import MODEL, LLMProvider
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

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
    # Taken from: https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#model-restrictions
    LLMProvider.SNOWFLAKE_CORTEX: {
        # We prefer these two
        "claude-3-5-sonnet": 18000,
        "deepseek-r1": 128000,

        # But we'll throw these in just in case
        # we need them
        "gemma-7b": 8000,
        "jamba-1.5-large": 256000,
        "jamba-1.5-mini": 256000,
        "jamba-instruct": 256000,
        "llama2-70b-chat": 4096,
        "llama3-70b": 8000,
        "llama3-8b": 8000,
        "llama3.1-405b": 128000,
        "llama3.1-70b": 128000,
        "llama3.1-8b": 128000,
        "llama3.2-1b": 128000,
        "llama3.2-3b": 128000,
        "llama3.3-70b": 128000,
        "mistral-7b": 32000,
        "mistral-large": 32000,
        "mistral-large2": 128000,
        "mixtral-8x7b": 32000,
        "reka-core": 32000,
        "reka-flash": 100000,
        "snowflake-arctic": 4096,
        "snowflake-llama-3.1-405b": 8000,
        "snowflake-llama-3.3-70b": 8000,
    },
}


class ContextStats(BaseModel):
    context_window_size: int
    tokens_per_message: dict[str, int]


class ContextSummary(BaseModel):
    context_window_size: int
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
        LLMProvider.SNOWFLAKE_CORTEX,
    ):
        raise ValueError(f"Unsupported model provider: {model.provider}")
    context_window_size = _get_context_window_size(model)
    messages = thread_state.get("values", {}).get("messages", [])
    return ContextStats(
        context_window_size=context_window_size,
        tokens_per_message=_count_tokens_per_message(model, messages),
    )


def _get_context_window_size(model: MODEL) -> int:
    match model.provider:
        case LLMProvider.OPENAI | LLMProvider.AMAZON | LLMProvider.SNOWFLAKE_CORTEX:
            try:
                return CONTEXT_WINDOW_SIZES.get(model.provider, {}).get(model.name)
            except KeyError:
                raise ValueError(f"Unsupported model name: {model.name}")
        case LLMProvider.AZURE:
            # We don't know which model is used so we return the most common size for GPTs
            return 128000
        case _:
            raise ValueError(f"Unsupported model provider: {model.provider}")


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
