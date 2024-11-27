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
        case LLMProvider.OPENAI | LLMProvider.AMAZON:
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
