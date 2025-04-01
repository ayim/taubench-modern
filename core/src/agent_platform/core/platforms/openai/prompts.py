from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.platforms.openai.types import (
    OpenAIPromptMessage,
    OpenAIPromptToolSpec,
)


@dataclass(frozen=True)
class OpenAIPrompt(PlatformPrompt):
    """A prompt for the OpenAI platform."""

    messages: list[OpenAIPromptMessage] | None = field(
        default_factory=list,
        metadata={
            "description": "The list of messages for the prompt.",
        },
    )
    """The list of messages for the prompt."""
    tools: list[OpenAIPromptToolSpec] | None = field(
        default_factory=list,
        metadata={
            "description": "The list of tools for the prompt.",
        },
    )
    """The list of tools for the prompt."""
    max_tokens: int = field(
        default=4096,
        metadata={
            "description": "The maximum number of tokens for the prompt.",
        },
    )
    """The maximum number of tokens for the prompt."""
    temperature: float = field(
        default=0.0,
        metadata={
            "description": "The temperature for the prompt.",
        },
    )
    """The temperature for the prompt."""
    top_p: float = field(
        default=1.0,
        metadata={
            "description": "The top p for the prompt.",
        },
    )
    """The top p for the prompt."""

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> dict:
        """Convert the prompt to a OpenAI request.

        Args:
            model: The OpenAI model to use.
            stream: Whether to return a stream request.

        Returns:
            A OpenAI request."""
        results_dict: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump() for message in self.messages]
            if self.messages
            else [],
        }

        if self.tools:
            results_dict["tools"] = [tool.model_dump() for tool in self.tools]

        return results_dict
