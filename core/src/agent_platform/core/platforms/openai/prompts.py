import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from openai.types.responses import (
        ResponseInputItemParam,
        ToolParam,
    )
    from openai.types.shared_params import Reasoning

from agent_platform.core.platforms.base import PlatformPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenAIPrompt(PlatformPrompt):
    """A prompt for the OpenAI platform."""

    input: list["ResponseInputItemParam"] = field(
        default_factory=list,
        metadata={
            "description": "The list of messages for the prompt.",
        },
    )
    """The list of messages for the prompt."""

    tools: list["ToolParam"] | None = field(
        default=None,
        metadata={
            "description": "The list of tools for the prompt.",
        },
    )
    """The list of tools for the prompt."""

    instructions: str | None = field(
        default=None,
        metadata={
            "description": "The instructions for the prompt.",
        },
    )
    """The instructions for the prompt."""

    max_output_tokens: int | None = field(
        default=None,
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

    tool_choice: Literal["auto", "required", "none"] = field(
        default="auto",
        metadata={
            "description": "The tools choice for the prompt.",
        },
    )
    """The tools choice for the prompt."""

    top_p: float = field(
        default=1.0,
        metadata={
            "description": "The top p for the prompt.",
        },
    )
    """The top p for the prompt."""

    reasoning: "Reasoning" = field(
        default_factory=lambda: {
            "effort": "medium",
            "summary": "detailed",
        },
        metadata={
            "description": "The reasoning for the prompt.",
        },
    )
    """The reasoning for the prompt."""

    include: list[str] = field(
        default_factory=lambda: [
            "reasoning.encrypted_content",
        ],
        metadata={
            "description": "The include for the prompt.",
        },
    )
    """The include for the prompt."""

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
            A OpenAI request.

        Note:
            OpenAI automatically enables prompt caching for requests with 1024+ tokens.
            For optimal caching, structure prompts with static content (system messages,
            instructions) at the beginning and dynamic content at the end.
        """
        logger.info(f"Using OpenAI model: {model}")
        results_dict: dict[str, Any] = {
            "model": model,
            "input": self.input,
            "tools": self.tools or [],
            "temperature": self.temperature,
            "tool_choice": self.tool_choice,
            "top_p": self.top_p,
            "reasoning": self.reasoning,
            "include": self.include,
            "store": False,
        }

        # Include max output tokens if provided
        if self.max_output_tokens is not None:
            results_dict["max_output_tokens"] = self.max_output_tokens

        # Include instructions if provided
        if self.instructions is not None:
            results_dict["instructions"] = self.instructions

        # Take last / segment piece of model name as the real model name
        if "/" in model:
            # This comes from, in the azure case, receiving a generic model ID here
            # (which is part of us gracefully handling missing model backing deployment
            # name, to preserve a level of backwards compatibility)
            model = model.split("/")[-1].strip()

        # This includes gpt-5.1 models
        can_reason = model.startswith("gpt-5") or model.startswith("o3") or model.startswith("o4")

        if can_reason:
            # No temp or top_p supported for reasoning models
            results_dict.pop("temperature")
            results_dict.pop("top_p")
            # Set the reasoning effort (default to medium if not provided)
            results_dict["reasoning"]["effort"] = self.reasoning.get("effort", "medium")
            logger.info(
                f"Using model {model} with reasoning effort {results_dict['reasoning']['effort']}",
            )
        else:
            logger.info(f"Using model {model} (no reasoning supported)")
            results_dict["reasoning"] = None
            results_dict["include"] = [
                inclusion
                for inclusion in self.include
                # CANNOT have this for non-reasoning models
                # leads to 400 errors, valid include params are
                # (see https://platform.openai.com/docs/api-reference/responses/create#responses-create-include):
                # - web_search_call.action.sources
                # - code_interpreter_call.outputs
                # - computer_call_output.output.image_url
                # - file_search_call.results
                # - message.input_image.image_url
                # - message.output_text.logprobs
                # - reasoning.encrypted_content
                if inclusion != "reasoning.encrypted_content"
            ]

        if self.tools:
            logger.info(f"Request includes {len(self.tools)} tools")

        if stream:
            results_dict["stream"] = True
            logger.info("Streaming enabled for this request")

        return results_dict
