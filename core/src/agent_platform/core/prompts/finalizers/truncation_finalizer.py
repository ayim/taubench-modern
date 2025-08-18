from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict, cast

import structlog

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
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

    truncation_token_floor: int = field(
        default=1_000,
        metadata=FieldMetadata(
            description="Minimum number of tokens to preserve when truncating tool results.",
        ),
    )
    """Minimum number of tokens to preserve when truncating tool results."""


class TruncationItem(TypedDict):
    tool_name: str
    tokens: int
    text_contents: list[PromptTextContent]


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
        truncation_token_floor: int | None = None,
        *args,
        **kwargs,
    ):
        if token_budget_percentage is None:
            token_budget_percentage = TruncationConfig.token_budget_percentage
        if truncation_token_floor is None:
            truncation_token_floor = TruncationConfig.truncation_token_floor

        self.token_budget_percentage = token_budget_percentage
        self.truncation_token_floor = truncation_token_floor
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

        Returns:
            The finalized list of messages with truncated content.
        """
        if not kernel:
            logger.warning("No kernel provided, skipping truncation")
            return messages

        # Merge initialized kwargs with the ones provided to __call__
        kwargs = {**self._kwargs, **kwargs}

        platform = kwargs.get("platform")
        if not platform:
            logger.warning("No platform provided, skipping truncation")
            return messages
        platform = cast("PlatformInterface", platform)

        # Sets default to one of the most common context windows.
        model_name = kwargs.get("model", "gpt-4-1")
        max_tokens = 128_000  # Default to 128k tokens
        try:
            max_tokens = platform.client.model_map.model_context_windows.get(model_name) or 128_000
        except (AttributeError, KeyError):
            logger.warning("No model context window found for model: %s", model_name)

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

        truncatable_content = self._collect_truncatable_content(messages)
        if not truncatable_content:
            logger.warning("No content found to truncate. Prompt will exceed token budget.")
            return messages

        # Sort by token count, with largest first
        truncatable_content.sort(key=lambda x: x["tokens"], reverse=True)

        # Log some info about the largest tool results.
        for item in truncatable_content[:3]:
            logger.info(f"Large Tool Result: {item['tool_name']} using {item['tokens']} tokens")

        # Apply truncation
        tokens_to_reduce = self._truncate_content(truncatable_content, tokens_to_reduce)

        # Recount tokens with the hydrated prompt (not the original one)
        new_token_count = hydrated_prompt.count_tokens_approx(model=model_name)
        logger.info(
            f"After truncation: {new_token_count} tokens "
            f"(reduced by {current_token_count - new_token_count})"
        )

        return messages

    def _collect_truncatable_content(self, messages: list["MessageType"]) -> list[TruncationItem]:
        """Collect tool results with content length greater than 0.

        Args:
            messages: List of messages to analyze

        Returns:
            List of dictionaries containing tool result information
        """
        truncatable_content: list[TruncationItem] = []

        for message in messages:
            if isinstance(message, SpecialPromptMessage):
                continue

            for content in message.content:
                if isinstance(content, PromptToolResultContent):
                    # Handle tool result content - extract text content for truncation
                    tool_token_count = content.count_tokens_approx()
                    if tool_token_count > 0:
                        # Extract any text content items from the tool result
                        text_contents = [
                            item for item in content.content if isinstance(item, PromptTextContent)
                        ]
                        # Only include if there are text contents with actual content
                        if text_contents and any(len(tc.text) > 0 for tc in text_contents):
                            truncatable_content.append(
                                TruncationItem(
                                    tool_name=content.tool_name,
                                    tokens=tool_token_count,
                                    text_contents=text_contents,
                                )
                            )

        return truncatable_content

    def _truncate_content(
        self, truncatable_content: list[TruncationItem], tokens_to_reduce: int
    ) -> int:
        """Proportionally truncate tool result contents based on the configured floor.

        This method distributes the token reduction across all tool results proportionally
        to their current size, while ensuring each tool result maintains at least
        the truncation_token_floor number of tokens.

        Args:
            truncatable_content: List of tool result content items to truncate
            tokens_to_reduce: Number of tokens that need to be reduced

        Returns:
            Remaining tokens that still need to be reduced (should be 0 or close to 0)
        """
        if not truncatable_content:
            return tokens_to_reduce

        # Calculate total tokens available for reduction (above the floor)
        total_reducible_tokens = 0
        for item in truncatable_content:
            current_tokens = item["tokens"]
            reducible_tokens = max(0, current_tokens - self.truncation_token_floor)
            total_reducible_tokens += reducible_tokens

        if total_reducible_tokens == 0:
            logger.warning("No tokens can be reduced while respecting the truncation floor")
            return tokens_to_reduce

        # Calculate how much we can actually reduce
        actual_tokens_to_reduce = min(tokens_to_reduce, total_reducible_tokens)

        logger.info(
            f"Proportionally reducing {actual_tokens_to_reduce} tokens across "
            f"{len(truncatable_content)} tool results (floor: {self.truncation_token_floor})"
        )

        # Apply proportional truncation to each item
        for item in truncatable_content:
            current_tokens = item["tokens"]
            reducible_tokens = max(0, current_tokens - self.truncation_token_floor)

            if reducible_tokens == 0:
                continue

            # Calculate this item's share of the reduction based on total reducible tokens
            share_ratio = reducible_tokens / total_reducible_tokens
            tokens_to_reduce_from_item = int(actual_tokens_to_reduce * share_ratio)
            # Ensure we never try to reduce more than what's reducible for this item
            tokens_to_reduce_from_item = min(tokens_to_reduce_from_item, reducible_tokens)

            if tokens_to_reduce_from_item <= 0:
                continue

            # Calculate target tokens for this item
            target_tokens = current_tokens - tokens_to_reduce_from_item
            target_tokens = max(target_tokens, self.truncation_token_floor)

            # Apply truncation to text contents within this item
            text_contents = item["text_contents"]
            if text_contents:
                self._truncate_item_to_target(item, target_tokens)

        return max(0, tokens_to_reduce - actual_tokens_to_reduce)

    def _truncate_item_to_target(self, item: TruncationItem, target_token_count: int) -> None:
        """Truncate a single tool result item to approximately the target token count.

        Args:
            item: The tool result item to truncate
            target_token_count: Target number of tokens for this item
        """
        if not item["text_contents"]:
            return

        if item["tokens"] <= target_token_count:
            return

        # Calculate reduction ratio for this item
        reduction_ratio = target_token_count / item["tokens"]

        for text_content in item["text_contents"]:
            # Estimate characters to keep based on token ratio
            # This is an approximation since token-to-character ratio varies
            chars_to_keep = int(len(text_content.text) * reduction_ratio)
            chars_to_keep = max(1, chars_to_keep)  # Keep at least 1 character

            if chars_to_keep < len(text_content.text):
                old_token_count, new_token_count = self._truncate_text_content(
                    text_content, chars_to_keep
                )
                tokens_saved = old_token_count - new_token_count

                logger.info(
                    f"Truncated tool result {item['tool_name']} from "
                    f"{old_token_count} to {new_token_count} tokens (saved {tokens_saved})"
                )

        # Update the item's token count after truncation.
        new_total_token_count = sum(tc.count_tokens_approx() for tc in item["text_contents"])
        item["tokens"] = new_total_token_count

    def _truncate_text_content(
        self, text_content: PromptTextContent, chars_to_keep: int
    ) -> tuple[int, int]:
        """Truncate a text content object and return tokens saved.

        Args:
            text_content: The text content to truncate
            chars_to_keep: Number of characters to keep

        Returns:
            Tuple of (old_token_count, new_token_count)
        """
        old_token_count = text_content.count_tokens_approx()

        truncated_text = (
            f"{text_content.text[:chars_to_keep]}... "
            f"[Tool result truncated due to length constraints]"
        )

        # Update the text content
        # We need to use __setattr__ because these are frozen dataclasses
        object.__setattr__(text_content, "text", truncated_text)

        new_token_count = text_content.count_tokens_approx()
        return old_token_count, new_token_count
