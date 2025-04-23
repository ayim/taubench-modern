import logging
from dataclasses import dataclass, field

from google.genai.types import Content, GenerateContentConfig, ThinkingConfig, Tool

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.platforms.google.configs import GoogleModelMap

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GooglePrompt(PlatformPrompt):
    """A prompt for the Google Gemini platform."""

    contents: list[Content] = field(
        default_factory=list,
        metadata={
            "description": "The contents for the prompt (including role and parts).",
        },
    )
    """The contents for the prompt (including role and parts)."""

    tools: list[Tool] | None = field(
        default=None,
        metadata={
            "description": "The list of tools for the prompt.",
        },
    )
    """The list of tools for the prompt."""

    max_output_tokens: int = field(
        default=4096,
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

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> dict[str, str | list[Content] | GenerateContentConfig]:
        """Convert the prompt to a Google Gemini request.

        Args:
            model: The Google model to use.
            stream: Whether to return a stream request.

        Returns:
            A Google Gemini request."""
        model_id = GoogleModelMap.model_aliases[model]
        logger.info(f"Using Google model: {model} (model_id: {model_id})")

        # Create the generation config
        generation_config_kwargs = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
        }
        thinking_budget = 0
        if "2.5" in model:
            if model.endswith("-high"):
                thinking_budget = 2048
                logger.info(f"Using {model} with high thinking budget (2048)")
            elif model.endswith("-low"):
                thinking_budget = 1024
                logger.info(f"Using {model} with low thinking budget (1024)")
            else:
                logger.info(f"Using {model} with default thinking budget (0)")
        else:
            logger.info(f"Using {model} with no thinking budget")

        if "2.5" in model:  # thinking_config is only supported on 2.5 models
            generation_config_kwargs["thinking_config"] = ThinkingConfig(
                thinking_budget=thinking_budget,
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
            "model": model_id,
            "contents": self.contents,
            "config": generation_config,
        }

        return results_dict
