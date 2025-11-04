# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Self

import structlog

from agent_platform.core.prompts.prompt import Prompt

if TYPE_CHECKING:
    from tenacity import RetryCallState

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.responses.response import ResponseMessage


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

EnhancementMode = Literal["full", "tables", "columns"]

TEMPERATURE = 0.5
MINIMIZE_REASONING = True


@dataclass
class PromptThread(Prompt):
    # Extended with functionality that allows us to more easily track the thread of enhancement
    # attempts for retry/improvement requests.

    def update_prompt_with_previous_try(self, retry_state: RetryCallState) -> None:
        """Update the prompt with the previous try's response and error if available."""
        from agent_platform.server.semantic_data_models.enhancer.errors import LLMResponseError

        if retry_state and retry_state.outcome and retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            if isinstance(exception, LLMResponseError):
                improvement_request = exception.improvement_request
                logger.info(f"Retrying with improvement request: {improvement_request[:400]}...")
                if exception.response_message:
                    self.append_response_and_error(exception.response_message, improvement_request)
                else:
                    raise ValueError("No response message available for retry")

    def append_response_and_error(
        self, response: ResponseMessage, improvement_request: str
    ) -> None:
        """Append the response and error to the prompt.

        We convert the response from the LLM to a PromptMessage so it can learn from it's mistake,
        this is how we can track the thread of enhancement attempts for retry/improvement requests.
        """
        from agent_platform.core.prompts.messages import (
            PromptAgentMessage,
            PromptTextContent,
            PromptUserMessage,
        )
        from agent_platform.server.semantic_data_models.enhancer.errors import EmptyResponseError
        from agent_platform.server.semantic_data_models.enhancer.parse import extract_response_text

        try:
            response_text = extract_response_text(response)
        except EmptyResponseError:
            # This shouldn't happen, but we'll just log it and move on.
            logger.warning(f"Empty response from LLM: {response}")
            # Use empty string as fallback
            response_text = ""

        agent_message = PromptAgentMessage(content=[PromptTextContent(text=response_text)])
        new_user_message = PromptUserMessage(content=[PromptTextContent(text=improvement_request)])
        self.extend_messages([agent_message, new_user_message])

    def copy(self) -> Self:
        """Return a deep copy of the prompt so it can be sent to the prompt_generate function."""
        from copy import deepcopy

        return deepcopy(self)


def create_enhancement_prompt(  # noqa: PLR0913
    semantic_model: SemanticDataModel,
    mode: EnhancementMode,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    *,
    temperature: float = TEMPERATURE,
    minimize_reasoning: bool = MINIMIZE_REASONING,
) -> PromptThread:
    """Create an enhancement prompt for a semantic data model."""
    from agent_platform.core.prompts.messages import PromptTextContent, PromptUserMessage
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.system_prompt import (
        render_system_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.user_prompt import (
        render_user_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        FULL_OUTPUT_SCHEMA_FORMAT,
        TABLES_OUTPUT_SCHEMA_FORMAT,
        TABLES_TO_COLUMNS_OUTPUT_SCHEMA_FORMAT,
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model,
    )
    match mode:
        case "full":
            output_schema = FULL_OUTPUT_SCHEMA_FORMAT
        case "tables":
            output_schema = TABLES_OUTPUT_SCHEMA_FORMAT
        case "columns":
            output_schema = TABLES_TO_COLUMNS_OUTPUT_SCHEMA_FORMAT
        case _:
            raise ValueError(f"Invalid mode: {mode}")
    system_message = render_system_prompt(
        mode=mode,
        tables_to_enhance=tables_to_enhance,
        table_to_columns_to_enhance=table_to_columns_to_enhance,
    )
    user_message = render_user_prompt(
        mode=mode,
        current_semantic_model=model_for_llm,
        output_schema=output_schema,
        tables_to_enhance=tables_to_enhance,
        table_to_columns_to_enhance=table_to_columns_to_enhance,
    )

    messages = [PromptUserMessage(content=[PromptTextContent(text=user_message)])]

    prompt = PromptThread(
        system_instruction=system_message,
        messages=messages,  # type: ignore
        temperature=temperature,
        minimize_reasoning=minimize_reasoning,
    )
    len_summary = f"""
    Len summary for the semantic data model enhancement prompt:
    system_prompt_length: {len(system_message)}
    user_prompt_length: {len(user_message)}
    mode: {mode}
    tables_to_enhance: {tables_to_enhance}
    table_to_columns_to_enhance: {table_to_columns_to_enhance}
    """
    logger.info(len_summary)
    return prompt


def create_quality_check_prompt(  # noqa: PLR0913
    enhanced_model: SemanticDataModel,
    *,
    mode: EnhancementMode = "full",
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    temperature: float = TEMPERATURE,
    minimize_reasoning: bool = MINIMIZE_REASONING,
) -> PromptThread:
    """Create a quality check prompt for a semantic data model."""
    import json

    from agent_platform.core.prompts.messages import PromptTextContent, PromptUserMessage
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_prompt import (
        render_quality_check_system_prompt,
    )
    from agent_platform.server.semantic_data_models.enhancer.prompt_templates.quality_check_user_prompt import (
        render_quality_check_user_prompt,
    )

    system_message = render_quality_check_system_prompt()
    user_message = render_quality_check_user_prompt(
        json.dumps(enhanced_model, indent=2),
        mode=mode,
        tables_to_enhance=tables_to_enhance,
        table_to_columns_to_enhance=table_to_columns_to_enhance,
    )
    messages = [PromptUserMessage(content=[PromptTextContent(text=user_message)])]
    prompt = PromptThread(
        system_instruction=system_message,
        messages=messages,  # type: ignore
        temperature=temperature,
        minimize_reasoning=minimize_reasoning,
    )
    len_summary = f"""
    Len summary for the semantic data model quality check prompt:
    system_prompt_length: {len(system_message)}
    user_prompt_length: {len(user_message)}
    """
    logger.info(len_summary)
    return prompt
