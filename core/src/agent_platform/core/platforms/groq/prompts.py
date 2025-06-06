import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from groq.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.platforms.groq.configs import GroqModelMap

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroqPrompt(PlatformPrompt):
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
        """Convert the prompt to a Groq request.

        Args:
            model: The Groq model to use.
            stream: Whether to return a stream request.

        Returns:
            A Groq request."""
        model_id = GroqModelMap.model_aliases[model]
        logger.info(f"Using Groq model: {model} (model_id: {model_id})")
        results_dict: dict[str, Any] = {
            "model": model_id,
            "messages": self.messages or [],
        }

        logger.info(f"Using model {model}")

        if self.tools:
            results_dict["tools"] = self.tools
            logger.info(f"Request includes {len(self.tools)} tools")

        if stream:
            results_dict["stream"] = True
            logger.info("Streaming enabled for this request")

        return results_dict
