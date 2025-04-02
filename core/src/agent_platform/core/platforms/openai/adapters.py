"""Adapters for OpenAI types.

This module provides adapter functions to convert between OpenAI SDK types and
the format required by our platform.
"""

from typing import Any

from openai.types import FunctionDefinition


def function_definition_to_tool_param(func_def: FunctionDefinition) -> dict[str, Any]:
    """Convert a FunctionDefinition to the tool format expected by OpenAI API.

    Args:
        func_def: The function definition from OpenAI.

    Returns:
        A dictionary in the format expected by the OpenAI API.
    """
    return {
        "type": "function",
        "function": {
            "name": func_def.name,
            "description": func_def.description or "",
            "parameters": func_def.parameters or {},
        },
    }


def format_message_for_api(
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Format a message for the OpenAI API.

    Args:
        role: The role of the message.
        content: The content of the message.
        tool_calls: Optional list of tool calls.

    Returns:
        A dictionary in the format expected by the OpenAI API.
    """
    message: dict[str, Any] = {"role": role, "content": content}
    if tool_calls and role == "assistant":
        message["tool_calls"] = tool_calls
    return message
