"""Utility functions for prompt-related operations."""

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from agent_platform.core.configurations import Configuration, FieldMetadata

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TokenCountingConfig(Configuration):
    """Configuration for token counting."""

    enable_tiktoken: bool = field(
        default=False,
        metadata=FieldMetadata(
            description="Whether to use tiktoken for token counting, defaults to False.",
            env_vars=["SEMA4AI_AGENT_SERVER_TOKEN_COUNTING_ENABLE_TIKTOKEN"],
        ),
    )
    """Whether to use tiktoken for token counting, defaults to False."""


def count_tokens_with_heuristic(
    text: str,
) -> int:
    """Counts the approximate number of tokens in the given text using a heuristic.

    Args:
        text: The text to count tokens for.

    Returns:
        int: Estimated token count
    """
    char_estimate = len(text) / 4
    word_estimate = len(text.split()) / 0.75
    return max(int(char_estimate), int(word_estimate))


def count_tokens_with_tiktoken(
    text: str,
    model: str = "gpt-3.5-turbo",
) -> int:
    """Counts the approximate number of tokens in the given text using tiktoken.

    Args:
        text: The text to count tokens for.
        model: The model to use for tiktoken encoding. Defaults to "gpt-3.5-turbo". If
            the model name is invalid, it will use "gpt-3.5-turbo" as a fallback.

    Returns:
        int: Estimated token count
    """
    try:
        import tiktoken

        # Use tiktoken for more accurate counting
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Invalid model name: {model}")
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))

    except Exception as e:
        logger.warning(f"Error counting tokens with tiktoken (will fall back to heuristic): {e}")
        return count_tokens_with_heuristic(text)


def count_tokens_approx(
    text: str,
    model: str = "gpt-3.5-turbo",
) -> int:
    """Counts the approximate number of tokens in the given text.

    This function attempts to use tiktoken (the OpenAI tokenizer) if available.
    Otherwise, it falls back to a heuristic calculation.

    Heuristic formula:
    - Takes the maximum of:
      - character count / 4 (1 token ~= 4 chars in English)
      - word count / 0.75 (1 token ~= 0.75 words)

    Args:
        text: The text to count tokens for.
        model: The model to use for tiktoken encoding. Defaults to "gpt-3.5-turbo". If
            the model name is invalid, it will use "gpt-3.5-turbo" as a fallback.

    Returns:
        int: Estimated token count
    """
    if TokenCountingConfig.enable_tiktoken:
        return count_tokens_with_tiktoken(text, model)
    else:
        return count_tokens_with_heuristic(text)


def format_tool_use_for_token_counting(
    tool_call_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    """Formats tool use information into a string for token counting.

    Args:
        tool_call_id: The unique identifier for the tool call.
        tool_name: The name of the tool being called.
        tool_input: The input parameters for the tool.

    Returns:
        str: A formatted string representation of the tool use.
    """
    content_str = f"tool_call_id: {tool_call_id}\n"
    content_str += f"tool_name: {tool_name}\n"
    content_str += f"tool_input: {json.dumps(tool_input)}"
    return content_str


def count_role_indicator_tokens(
    role: Literal["system", "user", "assistant"],
    model: str = "gpt-3.5-turbo",
) -> int:
    """Count tokens for a role indicator (system, user, assistant).

    Args:
        role: The role indicator to count tokens for.
        model: The model to use for tiktoken encoding. Defaults to "gpt-3.5-turbo".

    Returns:
        int: Number of tokens in the role indicator.
    """
    indicator = f"{role}: "
    return count_tokens_approx(indicator, model)


def count_tools_tokens(
    tools: list[dict[str, Any]] | list[Any],
    model: str = "gpt-3.5-turbo",
) -> int:
    """Count tokens for tool definitions.

    Args:
        tools: List of tool definitions (either dicts or ToolDefinition objects).
        model: The model to use for tiktoken encoding. Defaults to "gpt-3.5-turbo".

    Returns:
        int: Number of tokens in the tool definitions.
    """
    if not tools:
        return 0

    tools_text = "tools:\n"
    for tool in tools:
        # Handle both dictionary and object formats
        if isinstance(tool, dict):
            name = tool.get("name", "")
            description = tool.get("description", "")
            parameters = tool.get("parameters")
        else:
            # Assume it's a ToolDefinition-like object
            name = getattr(tool, "name", "")
            description = getattr(tool, "description", "")
            parameters = getattr(tool, "input_schema", None)

        tools_text += f"function: {name}\n"
        tools_text += f"description: {description}\n"
        if parameters:
            # Convert parameters to a string if it's not already
            if not isinstance(parameters, str):
                parameters_str = json.dumps(parameters)
            else:
                parameters_str = parameters
            tools_text += f"parameters: {parameters_str}\n"

    return count_tokens_approx(tools_text, model)
