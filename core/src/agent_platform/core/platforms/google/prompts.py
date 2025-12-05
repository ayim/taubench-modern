import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from agent_platform.core.platforms.base import PlatformPrompt

if TYPE_CHECKING:
    from google.genai.types import Content, GenerateContentConfig, Tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GooglePrompt(PlatformPrompt):
    """A prompt for the Google Gemini platform."""

    contents: "list[Content]" = field(
        default_factory=list,
        metadata={
            "description": "The contents for the prompt (including role and parts).",
        },
    )
    """The contents for the prompt (including role and parts)."""

    tools: "list[Tool] | None" = field(
        default=None,
        metadata={
            "description": "The list of tools for the prompt.",
        },
    )
    """The list of tools for the prompt."""

    max_output_tokens: int = field(
        default=4096,  # TODO: Revisit this in our Gemini client overhaul
        metadata={
            "description": "The maximum number of output tokens for the prompt.",
        },
    )
    """The maximum number of output tokens for the prompt."""

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

    thinking_budget: int = field(
        default=0,
        metadata={
            "description": "The thinking budget for the prompt.",
        },
    )
    """The thinking budget for the prompt."""

    thinking_level: str | None = field(
        default=None,
        metadata={
            "description": "Thinking level for Gemini 3 models (e.g., 'low' or 'high').",
        },
    )
    """The thinking level for Gemini 3 models."""

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> "dict[str, str | list[Content] | GenerateContentConfig]":
        """Convert the prompt to a Google Gemini request.

        Args:
            model: The Google model to use.
            stream: Whether to return a stream request.

        Returns:
            A Google Gemini request."""
        from google.genai.types import Content, GenerateContentConfig, ThinkingConfig

        logger.info(f"Using Google model: {model}")

        # Create the generation config
        generation_config_kwargs = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
        }

        if self.thinking_level or self.thinking_budget > 0:
            thinking_config_fields: dict[str, Any] = {}
            if self.thinking_level:
                thinking_config_fields["thinking_level"] = self.thinking_level
            if self.thinking_budget > 0:
                thinking_config_fields["thinking_budget"] = self.thinking_budget
                thinking_config_fields["include_thoughts"] = True
            generation_config_kwargs["thinking_config"] = ThinkingConfig(
                **thinking_config_fields,
            )

        # Add streaming parameter if requested
        if stream:
            logger.info("Streaming enabled for this request")

        # Add tools if available
        if self.tools:
            generation_config_kwargs.update(
                {
                    "tools": self.tools,
                },
            )
            logger.info("Request includes tools")

        # Create the generation config
        generation_config = GenerateContentConfig(**generation_config_kwargs)

        results_dict: dict[str, str | list[Content] | GenerateContentConfig] = {
            "model": model,
            "contents": self.contents,
            "config": generation_config,
        }

        return results_dict
