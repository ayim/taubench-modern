from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
from agent_platform.core.prompts.finalizers.base import BaseFinalizer
from agent_platform.core.prompts.messages import (
    PromptTextContent,
)
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.prompts.special.base import SpecialPromptMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel, PlatformInterface
    from agent_platform.core.prompts.finalizers.base import MessageType

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TruncationConfig(Configuration):
    """Configuration for the truncation finalizer."""

    token_budget_percentage: float = field(
        default=0.80,
        metadata=FieldMetadata(
            description="Percentage of model's context window to use.",
        ),
    )
    """Percentage of model's context window to use."""

    minimum_length_to_truncate: int = field(
        default=100,
        metadata=FieldMetadata(
            description="Minimum length to consider a message for "
            "truncation in tokens.",
        ),
    )
    """Minimum length to consider a message for truncation in tokens."""

    # TODO: Maybe this should be some percantage of what's available?
    max_content_length: int = field(
        default=10_000,
        metadata=FieldMetadata(
            description="Maximum length to truncate text content to in characters.",
        ),
    )
    """Maximum length to truncate text content to in characters."""


class TruncationFinalizer(BaseFinalizer):
    """
    Finalizer that truncates content in prompt messages to fit within
    a model's token budget.

    This finalizer is typically used to ensure that prompts sent to language
    models do not exceed the model's context window. It can be configured
    with a token budget percentage and a maximum content length.

    When called, the finalizer expects the following to be provided:
        - `messages`: List of PromptUserMessage or PromptAgentMessage
        - `prompt`: The Prompt instance being finalized
        - `kernel`: (optional) Kernel instance
        - `model`: (keyword, optional) Model identifier (e.g., "gpt-3.5-turbo")
        - `platform`: (keyword, optional) PlatformInterface instance (required
            for context window info)

    Usage:

    ```python
        truncation_finalizer = TruncationFinalizer()
        truncated_messages = truncation_finalizer(
            messages,
            prompt,
            kernel=kernel,
            model="gpt-3.5-turbo",
            platform=platform,
        )
    ```
    """

    def __init__(
        self,
        token_budget_percentage: float | None = None,
        minimum_length_to_truncate: int | None = None,
        max_content_length: int | None = None,
        *args,
        **kwargs,
    ):
        if token_budget_percentage is None:
            token_budget_percentage = TruncationConfig.token_budget_percentage
        if minimum_length_to_truncate is None:
            minimum_length_to_truncate = TruncationConfig.minimum_length_to_truncate
        if max_content_length is None:
            max_content_length = TruncationConfig.max_content_length

        self.token_budget_percentage = token_budget_percentage
        self.minimum_length_to_truncate = minimum_length_to_truncate
        self.max_content_length = max_content_length
        super().__init__(*args, **kwargs)

    async def __call__(
        self,
        messages: list["MessageType"],
        prompt: "Prompt",
        kernel: "Kernel | None" = None,
        **kwargs,
    ) -> list["MessageType"]:
        """
        Truncate content in messages to fit within the model's token budget.

        Args:
            messages: The list of messages to finalize.
            prompt: The prompt being finalized.
            kernel: The kernel instance (optional, but required for truncation).
            **kwargs: Additional keyword arguments:
                model: (str, optional) The model identifier (e.g., "gpt-3.5-turbo").
                platform: (PlatformInterface, optional) The platform to use
                    (required for context window info).
                model_name: (str, optional) Alternative to 'model'.

        Returns:
            The finalized list of messages with truncated content.
        """
        if not kernel:
            logger.warning("No kernel provided, skipping truncation")
            return messages

        # Merge initialized kwargs with the ones provided to __call__
        kwargs = {**self._kwargs, **kwargs}

        model_name = kwargs.get("model")
        if not model_name:
            model_name = kwargs.get("model_name", "gpt-3.5-turbo")

        platform: PlatformInterface | None = kwargs.get("platform")
        if not platform:
            logger.warning("No platform provided, skipping truncation")
            return messages

        max_tokens = platform.client.model_map.model_context_windows.get(model_name, 0)
        if not max_tokens:
            logger.warning(
                f"Unknown context window for model {model_name}, skipping truncation"
            )
            return messages

        max_token_budget = int(max_tokens * self.token_budget_percentage)

        # Create a copy of the prompt but with hydrated messages for token counting.
        # This ensures we include system instructions, tools, and other settings.
        hydrated_prompt = Prompt(
            system_instruction=prompt.system_instruction,
            messages=list(messages),  # type: ignore
            tools=prompt.tools,
            tool_choice=prompt.tool_choice,
            temperature=prompt.temperature,
            seed=prompt.seed,
            max_output_tokens=prompt.max_output_tokens,
            stop_sequences=prompt.stop_sequences,
            top_p=prompt.top_p,
        )
        current_token_count = hydrated_prompt.count_tokens_approx(model=model_name)

        if current_token_count <= max_token_budget:
            return messages

        tokens_to_reduce = current_token_count - max_token_budget
        logger.info(
            f"Prompt exceeds token budget. Current: {current_token_count}, "
            f"Max: {max_token_budget}, Need to reduce by: {tokens_to_reduce}"
        )

        # Collect both tool results and large text content
        truncatable_content = self._collect_truncatable_content(messages)
        if not truncatable_content:
            logger.warning(
                "No content found to truncate. Prompt will exceed token budget."
            )
            return messages

        # Sort by token count, with largest first
        truncatable_content.sort(key=lambda x: x["tokens"], reverse=True)

        # Log some info about the largest content items
        for item in truncatable_content[:3]:
            item_type = "tool result" if item.get("tool_name") else "text content"
            name = item.get("tool_name", "text")
            logger.info(f"Large {item_type}: {name} using {item['tokens']} tokens")

        # Apply truncation
        tokens_to_reduce = self._truncate_content(truncatable_content, tokens_to_reduce)

        # Recount tokens with the hydrated prompt (not the original one)
        new_token_count = hydrated_prompt.count_tokens_approx(model=model_name)
        logger.info(
            f"After truncation: {new_token_count} tokens "
            f"(reduced by {current_token_count - new_token_count})"
        )

        return messages

    def _truncate_content(
        self, truncatable_content: list[dict], tokens_to_reduce: int
    ) -> int:
        """Truncate the largest content items until the token budget is met."""
        for item in truncatable_content:
            if tokens_to_reduce <= 0:
                break

            text_contents = item.get("text_contents", [])
            if not text_contents:
                continue

            for text_content in text_contents:
                # Directly use max_content_length as the primary constraint.
                chars_to_keep = min(len(text_content.text), self.max_content_length)

                if chars_to_keep < len(text_content.text):
                    old_tokens, new_tokens = self._truncate_text_content(
                        text_content, chars_to_keep
                    )
                    tokens_saved = old_tokens - new_tokens
                    tokens_to_reduce -= tokens_saved

                    # Log the truncation
                    item_type = (
                        "tool result" if item.get("tool_name") else "text content"
                    )
                    name = item.get("tool_name", "text")
                    logger.info(
                        f"Truncated {item_type} {name} from "
                        f"{old_tokens} to {new_tokens} tokens (saved {tokens_saved})"
                    )

                    if tokens_to_reduce <= 0:
                        break
        return tokens_to_reduce

    def _collect_truncatable_content(
        self, messages: list["MessageType"]
    ) -> list[dict[str, Any]]:
        """Collect all potentially truncatable content from messages with
        their token counts.

        This includes both tool results and large text content.

        Args:
            messages: List of messages to analyze

        Returns:
            List of dictionaries containing content information
        """
        truncatable_content = []

        for message_idx, message in enumerate(messages):
            if isinstance(message, SpecialPromptMessage):
                continue

            for content_idx, content in enumerate(message.content):
                if isinstance(content, PromptTextContent):
                    # Handle regular text content in agent messages
                    text_token_count = content.count_tokens_approx()
                    if text_token_count > self.minimum_length_to_truncate:
                        truncatable_content.append(
                            {
                                "message_idx": message_idx,
                                "message": message,
                                "content_idx": content_idx,
                                "content": content,
                                "tokens": text_token_count,
                                "text_contents": [content],
                            }
                        )
                elif isinstance(content, PromptToolResultContent):
                    # Handle tool result content - extract text content for truncation
                    tool_token_count = content.count_tokens_approx()
                    if tool_token_count > self.minimum_length_to_truncate:
                        # Extract any text content items from the tool result
                        text_contents = [
                            item
                            for item in content.content
                            if isinstance(item, PromptTextContent)
                        ]
                        truncatable_content.append(
                            {
                                "message_idx": message_idx,
                                "message": message,
                                "content_idx": content_idx,
                                "content": content,
                                "tool_name": content.tool_name,
                                "tokens": tool_token_count,
                                "text_contents": text_contents,
                            }
                        )
                elif isinstance(content, PromptToolUseContent):
                    # Handle tool use content
                    tool_token_count = content.count_tokens_approx()
                    if tool_token_count > self.minimum_length_to_truncate:
                        truncatable_content.append(
                            {
                                "message_idx": message_idx,
                                "message": message,
                                "content_idx": content_idx,
                                "content": content,
                                "tool_name": content.tool_name,
                                "tokens": tool_token_count,
                                # Tool use typically doesn't have text to truncate
                                "text_contents": [],
                            }
                        )

        return truncatable_content

    def _truncate_text_content(
        self, text_content: PromptTextContent, chars_to_keep: int
    ) -> tuple[int, int]:
        """Truncate a text content object and return tokens saved.

        Args:
            text_content: The text content to truncate
            chars_to_keep: Number of characters to keep

        Returns:
            Tuple of (old_tokens, new_tokens)
        """
        old_tokens = text_content.count_tokens_approx()

        # More aggressively truncate by respecting the chars_to_keep limit
        # without any additional logic that might expand it
        truncated_text = (
            f"{text_content.text[:chars_to_keep]}... "
            f"[Tool result truncated due to length constraints]"
        )

        # Update the text content
        # We need to use __setattr__ because these are frozen dataclasses
        object.__setattr__(text_content, "text", truncated_text)

        new_tokens = text_content.count_tokens_approx()
        return old_tokens, new_tokens
