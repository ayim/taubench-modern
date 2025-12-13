from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict, cast

import structlog

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.platforms.configs import PlatformModelConfigs
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

    text_truncation_token_floor: int = field(
        default=512,
        metadata=FieldMetadata(
            description="Minimum number of tokens to preserve when truncating plain text.",
        ),
    )
    """Minimum number of tokens to preserve when truncating plain text."""

    truncation_suffix: str = field(
        default="[Truncated...]",
        metadata=FieldMetadata(
            description="Suffix to add to truncated text.",
        ),
    )
    """Suffix to add to truncated text."""

    max_truncation_passes: int = field(
        default=3,
        metadata=FieldMetadata(
            description="Maximum number of truncation passes to perform.",
        ),
    )
    """Maximum number of truncation passes to perform."""


class TruncationItem(TypedDict):
    # tool_name is empty string ("") for non-tool text items
    tool_name: str
    tokens: int
    text_contents: list[PromptTextContent]
    # lower index == older message
    message_index: int
    # "tool" or "text" (plain PromptTextContent)
    item_type: Literal["tool", "text"]
    # per-item floor (tool vs text)
    floor: int


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

    Behavior:
        - Collects truncatable content from:
          * Tool results (only their inner PromptTextContent portions)
          * Plain top-level PromptTextContent (non-tool)
        - Prefers truncating **older** messages first (lower message_index).
        - Respects per-item floors (tool vs plain text).

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
        text_truncation_token_floor: int | None = None,
        truncation_suffix: str | None = None,
        max_truncation_passes: int | None = None,
        *args,
        **kwargs,
    ):
        if token_budget_percentage is None:
            token_budget_percentage = TruncationConfig.token_budget_percentage
        if truncation_token_floor is None:
            truncation_token_floor = TruncationConfig.truncation_token_floor
        if text_truncation_token_floor is None:
            text_truncation_token_floor = TruncationConfig.text_truncation_token_floor
        if truncation_suffix is None:
            truncation_suffix = TruncationConfig.truncation_suffix
        if max_truncation_passes is None:
            max_truncation_passes = TruncationConfig.max_truncation_passes

        self.token_budget_percentage = token_budget_percentage
        self.truncation_token_floor = truncation_token_floor
        self.text_truncation_token_floor = text_truncation_token_floor
        self.truncation_suffix = truncation_suffix
        self.max_truncation_passes = max_truncation_passes
        # Cache the suffix token cost during initialization
        self._suffix_token_cost = PromptTextContent(text=self.truncation_suffix).count_tokens_approx() + 10
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

        model_name = kwargs.get("model", "gpt-4-1")
        try:
            max_tokens = (
                PlatformModelConfigs.models_to_context_window_sizes.get(model_name, None)
                or platform.client.model_map.model_context_windows.get(model_name, None)
                or 128_000
            )
            logger.info(f"Using model context window: {max_tokens} tokens for model: {model_name}")
        except (AttributeError, KeyError):
            logger.warning(f"No model context window found for model: {model_name}")
            logger.warning("Falling back to default context window of 128_000 tokens")
            max_tokens = 128_000

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
        current_token_count = hydrated_prompt.count_tokens_approx()

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

        # Log some info about the largest items (by tokens) for visibility.
        for item in sorted(truncatable_content, key=lambda x: x["tokens"], reverse=True)[:3]:
            label = f"{item['item_type']}:{item['tool_name']}" if item["item_type"] == "tool" else "text"
            logger.info(f"Largest truncatable item -> {label} using {item['tokens']} tokens")

        # Apply truncation (oldest-first greedy with per-item floors)
        remaining = self._truncate_content(truncatable_content, tokens_to_reduce)
        passes = 1
        while remaining > 0 and passes < self.max_truncation_passes:
            prev = remaining
            remaining = self._truncate_content(truncatable_content, remaining)
            # No progress? break to avoid spin
            if remaining >= prev:
                break
            passes += 1

        # Recount tokens with the hydrated prompt (not the original one)
        new_token_count = hydrated_prompt.count_tokens_approx()
        logger.info(f"After truncation: {new_token_count} tokens (reduced by {current_token_count - new_token_count})")

        return messages

    def _collect_truncatable_content(self, messages: list["MessageType"]) -> list[TruncationItem]:
        """Collect tool results and plain text contents with length > 0.

        Args:
            messages: List of messages to analyze

        Returns:
            List of dictionaries containing truncation info
        """
        truncatable_content: list[TruncationItem] = []
        first_user_message_index = next(
            (idx for idx, msg in enumerate(messages) if getattr(msg, "role", None) == "user"),
            None,
        )

        for msg_idx, message in enumerate(messages):
            if isinstance(message, SpecialPromptMessage):
                continue

            if first_user_message_index is not None and msg_idx == first_user_message_index:
                # Preserve the very first user instructions entirely.
                continue

            for content in message.content:
                if isinstance(content, PromptToolResultContent):
                    # Extract only text items from the tool result (what we can actually shrink)
                    text_contents = [item for item in content.content if isinstance(item, PromptTextContent)]
                    tool_text_tokens = sum(tc.count_tokens_approx() for tc in text_contents)
                    if text_contents and tool_text_tokens > 0 and any(tc.text for tc in text_contents):
                        truncatable_content.append(
                            TruncationItem(
                                tool_name=content.tool_name,
                                tokens=tool_text_tokens,
                                text_contents=text_contents,
                                message_index=msg_idx,
                                item_type="tool",
                                floor=self.truncation_token_floor,
                            )
                        )
                elif isinstance(content, PromptTextContent):
                    # Plain top-level text content (non-tool)
                    tok = content.count_tokens_approx()
                    if tok > 0 and content.text:
                        truncatable_content.append(
                            TruncationItem(
                                tool_name="",
                                tokens=tok,
                                text_contents=[content],
                                message_index=msg_idx,
                                item_type="text",
                                floor=self.text_truncation_token_floor,
                            )
                        )

        return truncatable_content

    def _truncate_content(
        self,
        truncatable_content: list[TruncationItem],
        tokens_to_reduce: int,
    ) -> int:
        """Greedy oldest-first truncation with per-item floors.

        We walk items ordered by (older first, larger first) and reduce each
        item toward its floor until we satisfy the reduction or run out of room.
        """
        if not truncatable_content or tokens_to_reduce <= 0:
            return tokens_to_reduce

        # Prioritize tool content before user text so we don't drop early
        # conversational context just because it happened earlier.
        def sort_key(item: TruncationItem) -> tuple[int, int, int]:
            item_priority = 0 if item["item_type"] == "tool" else 1
            return (item_priority, item["message_index"], -item["tokens"])

        ordered = sorted(truncatable_content, key=sort_key)

        remaining = tokens_to_reduce
        for item in ordered:
            if remaining <= 0:
                break

            current_tokens = item["tokens"]
            reducible = max(0, current_tokens - item["floor"])
            if reducible <= 0:
                continue

            take = min(remaining, reducible) + self._suffix_token_cost
            target_tokens = current_tokens - take
            target_tokens = max(target_tokens, item["floor"])

            # Apply truncation to this item
            self._truncate_item_to_target(item, target_tokens)

            # Update remaining based on actual savings
            saved = max(0, current_tokens - item["tokens"])
            remaining -= saved

            label = f"{item['item_type']}:{item['tool_name']}" if item["item_type"] == "tool" else "text"
            logger.info(
                f"Oldest-first truncation -> {label} "
                f"(msg #{item['message_index']}): {current_tokens} "
                f"-> {item['tokens']} (saved {saved})"
            )

        if remaining > 0:
            logger.warning(
                f"Unable to meet full reduction while respecting floors. Remaining: {remaining}",
            )
        return remaining

    def _truncate_item_to_target(self, item: TruncationItem, target_token_count: int) -> None:
        """Truncate a single item (tool result text or plain text) to approx the target token count.

        Args:
            item: The truncation item
            target_token_count: Target number of tokens for this item
        """
        if not item["text_contents"]:
            return

        # Recompute current tokens in case prior passes mutated content
        current_tokens = sum(tc.count_tokens_approx() for tc in item["text_contents"])
        if current_tokens <= target_token_count:
            item["tokens"] = current_tokens
            return

        # Avoid division by zero; if there's content but token count is 0, do nothing.
        if current_tokens <= 0:
            item["tokens"] = 0
            return

        # Calculate reduction ratio for this item
        reduction_ratio = max(0.0, min(1.0, target_token_count / current_tokens))

        for text_content in item["text_contents"]:
            original_len = len(text_content.text)
            if original_len == 0:
                continue

            # Estimate characters to keep based on token ratio
            # This is an approximation since token-to-character ratio varies
            chars_to_keep = int(original_len * reduction_ratio)
            chars_to_keep = max(
                1,
                min(chars_to_keep, original_len),
            )  # Keep at least 1 char, at most length

            if chars_to_keep < original_len:
                old_token_count, new_token_count = self._truncate_text_content(text_content, chars_to_keep)
                tokens_saved = old_token_count - new_token_count
                if tokens_saved > 0:
                    logger.info(
                        f"Truncated {item['item_type']}:{item['tool_name'] or 'text'} "
                        f"from {old_token_count} to {new_token_count} tokens "
                        f"(saved {tokens_saved})"
                    )

        # Update the item's token count after truncation (sum of text contents).
        item["tokens"] = sum(tc.count_tokens_approx() for tc in item["text_contents"])

    def _truncate_text_content(self, text_content: PromptTextContent, chars_to_keep: int) -> tuple[int, int]:
        """Truncate a text content object and return tokens saved.

        Args:
            text_content: The text content to truncate
            chars_to_keep: Number of characters to keep

        Returns:
            Tuple of (old_token_count, new_token_count)
        """
        old_token_count = text_content.count_tokens_approx()

        truncated_text = f"{text_content.text[:chars_to_keep]}{self.truncation_suffix}"

        # Update the text content
        # We need to use __setattr__ because these are frozen dataclasses
        object.__setattr__(text_content, "text", truncated_text)

        new_token_count = text_content.count_tokens_approx()
        return old_token_count, new_token_count
