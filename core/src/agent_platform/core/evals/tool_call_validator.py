"""Utilities for validating tool call drift with optional language model assistance."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from agent_platform.core.prompts import Prompt, PromptUserMessage
from agent_platform.core.prompts.content import PromptTextContent
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface


logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ToolCallValidationContext:
    """Input payload describing a drift between expected and actual tool call."""

    tool_name: str
    expected_args: dict[str, Any]
    actual_args: dict[str, Any]
    expected_output: Any
    expected_error: str | None
    tool_definition: ToolDefinition | None = None


@dataclass(frozen=True)
class ToolCallValidationDecision:
    """Result produced by a tool call validator."""

    accepted: bool
    reason: str
    proposed_output: Any | None = None
    proposed_error: str | None = None
    raw_response: str | None = None


class ToolCallValidator(ABC):
    """Base class for resolving tool call drifts."""

    def attach_kernel(self, kernel: Kernel) -> None:
        """Attach the active kernel when available."""
        return None

    @abstractmethod
    async def validate(self, context: ToolCallValidationContext) -> ToolCallValidationDecision | None:
        """Evaluate a tool call drift."""
        raise NotImplementedError


class LanguageModelToolCallValidator(ToolCallValidator):
    """Tool drift validator that queries a language model for guidance."""

    def __init__(
        self,
    ) -> None:
        self._kernel: Kernel | None = None

    def attach_kernel(self, kernel: Kernel) -> None:
        """Record the kernel for later model access."""
        self._kernel = kernel

    async def validate(self, context: ToolCallValidationContext) -> ToolCallValidationDecision | None:
        """Validate drift with a language model if possible."""
        if self._kernel is None:
            logger.debug("Skipping LLM drift validation; kernel not attached")
            return None

        selection = await self._select_platform_and_model()
        if selection is None:
            logger.warning("No platform/model available for drift validation")
            return ToolCallValidationDecision(
                accepted=False,
                reason="no language model available",
            )

        platform, model = selection
        prompt = self._build_prompt(context)

        try:
            response = await platform.generate_response(prompt, model)
        except Exception as exc:
            logger.exception("Language model validation failed", exc_info=exc)
            return ToolCallValidationDecision(
                accepted=False,
                reason=f"language model call failed: {exc}",
            )

        raw_text = self._extract_text_response(response)

        if raw_text is None:
            logger.warning("Language model produced no textual response")
            return ToolCallValidationDecision(
                accepted=False,
                reason="language model returned no text",
            )

        logger.debug(f'LM response: "{raw_text}"')

        parsed = self._parse_json_response(raw_text)
        if parsed is None:
            logger.warning("Language model response was not valid JSON", response=raw_text)
            return ToolCallValidationDecision(
                accepted=False,
                reason="language model response was not valid JSON",
                raw_response=raw_text,
            )

        accepted = bool(parsed.get("valid"))
        reason = str(parsed.get("reason") or parsed.get("explanation") or "")
        proposed_output = parsed.get("output") if accepted else None
        proposed_error = parsed.get("error") if accepted else None

        return ToolCallValidationDecision(
            accepted=accepted,
            reason=reason or ("accepted" if accepted else "rejected by language model"),
            proposed_output=proposed_output,
            proposed_error=proposed_error,
            raw_response=raw_text,
        )

    async def _select_platform_and_model(self) -> tuple[PlatformInterface, str] | None:
        kernel = self._kernel
        if kernel is None:
            return None

        try:
            return await kernel.get_platform_and_model(model_type="llm")
        except Exception as exc:
            logger.warning("Failed to select platform/model for drift validation", exc_info=exc)
            return None

    @staticmethod
    def _format_json(data: Any) -> str:
        try:
            return json.dumps(data, indent=2, sort_keys=True)
        except TypeError:
            return json.dumps(data, indent=2)

    def _build_prompt(self, context: ToolCallValidationContext) -> Prompt:
        tool_definition = context.tool_definition
        description = tool_definition.description if tool_definition else "(no description)"
        input_schema = (
            self._format_json(tool_definition.input_schema)
            if tool_definition and tool_definition.input_schema
            else "(no schema available)"
        )
        expected_args = self._format_json(context.expected_args)
        actual_args = self._format_json(context.actual_args)
        expected_output = self._format_json(context.expected_output)
        expected_error = context.expected_error or "null"

        instructions = "\n".join(
            [
                "You validate whether a tool call with differing arguments should be accepted.",
                "Compare the expected and actual arguments along with the tool definition.",
                "# CRITERIA",
                "## ARGUMENT EQUIVALENCE and NORMALIZATION",
                "- Case/whitespace/Unicode-normalization doesn't change meaning.",
                "- Order-insensitive collections compare equal as sets.",
                "- Units & formats normalize (e.g. ISO-8601 for times).",
                "- Aliases map to same field (e.g., q = query, limit = max_results).",
                "## PAGINATION, SORTING, PROJECTION, FILTERS",
                "- Arguments with the same meaning are allowed",
                "- Pagination changes allowed if you can deterministically slice:",
                "\t - If requested N ≤ recorded_count, then trim to N.",
                "\t - If requested N > recorded_count, then generate syntetic data or reject.",
                "- Sort changes allowed if sortable keys exist in recorded output, ",
                "then reorder deterministically; else reject.",
                "- Field projection allowed if requested fields contained in recorded fields, "
                "then drop extras; else reject.",
                "otherwise trim it to the requested total",
                "- Filters are logically equivalent (e.g., price<=10 = max_price:10)"
                "- Narrowed filters accepted if golden output is a superset ",
                "(i.e., can filter down deterministically).",
                "- Broadened filters only accepted only if output ",
                "can be fabricated based on golden output.",
                "## OUTPUT REUSE",
                "- Reuse “as-is” when args are semantically equivalent.",
                "- if new args require data not present in golden output, ",
                "fabricate based on golden or reject.",
                "# DETAILS",
                f"Tool name: {context.tool_name}",
                f"Tool description: {description}",
                f"Input schema: {input_schema}",
                f"Expected arguments: {expected_args}",
                f"Actual arguments: {actual_args}",
                f"Recorded output: {expected_output}",
                f"Recorded error: {expected_error}",
                "# RESPONSE FORMATRespond with a strict JSON object containing the keys: valid (boolean),",
                "reason (string explanation), output (JSON value to return if valid, null if the",
                "recorded output should be reused), and error (string or null).",
                "Output RAW JSON only. Do not use code fences, markdown, or language tags.",
                'The first character must be "{" and the last must be "}".',
            ]
        )

        logger.debug(f"instructions: {instructions}")

        message = PromptUserMessage(
            content=[
                PromptTextContent(
                    text=instructions,
                ),
            ],
        )

        return Prompt(
            system_instruction="You are a meticulous JSON-only validator for tool call drift.",
            messages=[message],
            temperature=0.0,
            max_output_tokens=600,
        )

    @staticmethod
    def _extract_text_response(response) -> str | None:
        from agent_platform.core.responses.content.text import ResponseTextContent

        texts = [item.text for item in response.content if isinstance(item, ResponseTextContent)]
        if not texts:
            return None
        return "\n".join(texts).strip()

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict[str, Any] | None:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            return None
