from dataclasses import dataclass
from typing import Any

from agent_platform.core.platforms.base import PlatformPrompt


@dataclass(frozen=True)
class AzureFoundryPrompt(PlatformPrompt):
    """A prompt for the Azure Foundry platform.

    This class stores the prompt in the format expected by the Anthropic Messages API
    as used through Azure AI Foundry.
    """

    messages: list[dict[str, Any]] | None = None
    system: str | list[dict[str, Any]] | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    stop_sequences: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None
    thinking: dict[str, Any] | None = None
    betas: list[str] | None = None

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Convert the prompt to an Anthropic Messages API request.

        Args:
            model: The model ID to use for the request.

        Returns:
            A dictionary suitable for the Anthropic Messages API.
        """
        request: dict[str, Any] = {
            "model": model,
            "messages": self.messages or [],
        }

        if self.system is not None:
            request["system"] = self.system
        if self.max_tokens is not None:
            request["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.top_p is not None:
            request["top_p"] = self.top_p
        if self.stop_sequences is not None:
            request["stop_sequences"] = self.stop_sequences
        if self.tools is not None:
            request["tools"] = self.tools
        if self.tool_choice is not None:
            request["tool_choice"] = self.tool_choice
        if self.thinking is not None:
            request["thinking"] = self.thinking

        return request
