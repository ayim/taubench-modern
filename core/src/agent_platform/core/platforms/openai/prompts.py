import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.platforms.openai.configs import OpenAIModelMap

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenAIPrompt(PlatformPrompt):
    """A prompt for the OpenAI platform."""

    messages: list["ChatCompletionMessageParam"] = field(
        default_factory=list,
        metadata={
            "description": "The list of messages for the prompt.",
        },
    )
    """The list of messages for the prompt."""

    tools: list["ChatCompletionToolParam"] | None = field(
        default=None,
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
    ) -> dict[str, Any]:
        """Convert the prompt to a OpenAI request.

        Args:
            model: The OpenAI model to use.
            stream: Whether to return a stream request.

        Returns:
            A OpenAI request."""
        model_id = OpenAIModelMap.model_aliases[model]
        logger.info(f"Using OpenAI model: {model} (model_id: {model_id})")
        results_dict: dict[str, Any] = {
            "model": model_id,
            "messages": self.messages or [],
        }

        if any(
            # It's a bit odd right now, o3-mini and o1 have reasoning effort
            # For o1-mini it's either o1-mini-high or o1-mini-low (as the model
            # name, no reasoning effort param supported)
            model.startswith(prefix) and not model.startswith("o1-mini-")
            for prefix in ["o3-mini", "o1"]
        ):
            # For o1/o3 models, adjust temperature based on high/low reasoning
            if model.endswith("-high"):
                results_dict["reasoning_effort"] = "high"
                logger.info(f"Using model {model} with high reasoning effort")
            elif model.endswith("-low"):
                results_dict["reasoning_effort"] = "low"
                logger.info(f"Using model {model} with low reasoning effort")
            else:
                logger.info(f"Using model {model} with default reasoning effort")
        else:
            logger.info(f"Using model {model}")

        if self.tools:
            results_dict["tools"] = self.tools
            logger.info(f"Request includes {len(self.tools)} tools")

        if stream:
            results_dict["stream"] = True
            logger.info("Streaming enabled for this request")

        return results_dict
