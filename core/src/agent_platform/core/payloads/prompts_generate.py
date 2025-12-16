"""Payload for prompts generate requests from transport layer."""

from typing import TYPE_CHECKING, Any, TypedDict

from agent_platform.core.platforms.configs import ModelType

if TYPE_CHECKING:
    from agent_platform.core.prompts import Prompt


class PromptsGeneratePayload(TypedDict, total=False):
    prompt: "Prompt | dict[str, Any]"
    """The prompt specification as a Prompt instance or dictionary (will be validated as Prompt)."""

    platform_config: dict[str, Any]
    """Platform configuration dictionary (required)."""

    model: str | None
    """Optional model name to use for generation."""

    model_type: ModelType
    """Model type, defaults to 'llm'."""
