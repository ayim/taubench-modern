from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.platforms.cortex.types import (
    CortexPromptMessage,
    CortexPromptToolSpec,
)


@dataclass(frozen=True)
class CortexPrompt(PlatformPrompt):
    """A prompt for the Cortex platform.

    This class stores the prompt in the format expected by the Cortex API.
    """

    messages: list[CortexPromptMessage] | None = field(
        default_factory=list,
        metadata={
            "description": "The list of messages for the prompt.",
        },
    )
    """The list of messages for the prompt."""

    tools: list[CortexPromptToolSpec] | None = field(
        default_factory=list,
        metadata={
            "description": "The list of tools for the prompt.",
        },
    )
    """The list of tools for the prompt."""

    max_tokens: int = field(
        default=16384,  # 16384 is the default max tokens for Cortex (from their API docs)
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
        """Convert the prompt to a Cortex request.

        Args:
            model: The Bedrock model ID to use to generate the request.
            stream: Whether to return a stream request.

        Returns:
            A Cortex request.
        """

        results_dict: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump() for message in self.messages] if self.messages else [],
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "stream": stream,
        }

        if self.tools:
            results_dict["tools"] = [{"tool_spec": tool.model_dump()} for tool in self.tools]

        return results_dict
