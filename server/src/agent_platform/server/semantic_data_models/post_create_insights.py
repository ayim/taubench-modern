"""Helpers for SDM post-create insights and thread messaging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger
from structlog.stdlib import BoundLogger

if TYPE_CHECKING:
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.api.dependencies import StorageDependency
    from agent_platform.server.auth import AuthedUser

logger: BoundLogger = get_logger(__name__)

MIN_SUGGESTED_QUESTIONS = 3
SDM_QUESTION_SYSTEM_PROMPT = (
    "You are a data assistant. Generate three concise natural-language questions "
    "a user can ask about the provided Semantic Data Model. Return ONLY a JSON array "
    "of three strings. Do not include any other text."
)


def _normalize_sdm_dict(semantic_model: SemanticDataModel) -> dict:
    """Normalize SDM payload to a dictionary for safe access."""
    return semantic_model.model_dump()


def build_sdm_post_create_summary(
    semantic_model: SemanticDataModel,
    model_name: str,
) -> str:
    """Build a short, deterministic SDM summary for post-create messaging.

    Args:
        semantic_model: The semantic data model payload.
        model_name: The resolved model name to include in the summary.

    Returns:
        A short multi-sentence summary suitable for a chat message.
    """
    sdm_dict = _normalize_sdm_dict(semantic_model)
    tables = sdm_dict.get("tables") or []
    relationships = sdm_dict.get("relationships") or []
    table_count = len(tables)
    relationship_count = len(relationships)

    table_label = "table" if table_count == 1 else "tables"
    relationship_label = "relationship" if relationship_count == 1 else "relationships"

    summary_lines = [
        f'Created a Semantic Data Model called "{model_name}".',
        f"It includes {table_count} {table_label} and {relationship_count} {relationship_label}.",
        "Ask a question about your data.",
    ]
    return " ".join(summary_lines)


def _format_sdm_for_question_prompt(semantic_model: SemanticDataModel) -> str:
    """Format SDM details into a prompt-friendly string."""
    from agent_platform.server.kernel.semantic_data_model import summarize_data_model

    return summarize_data_model(semantic_model, None)


def _parse_sdm_questions_from_llm(text: str) -> list[str]:
    """Parse a JSON array of questions from the LLM response."""
    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse SDM questions from LLM output", error="invalid_json")
        return []

    if not isinstance(parsed, list):
        logger.warning("Failed to parse SDM questions from LLM output", error="not_a_list")
        return []

    questions: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                questions.append(stripped)

    return questions


async def _generate_sdm_questions_via_llm(
    *,
    semantic_model: SemanticDataModel,
    user: AuthedUser,
    storage: StorageDependency,
    thread: Thread,
    temperature: float | None = None,
    minimize_reasoning: bool | None = None,
) -> list[str]:
    """Generate suggested SDM questions via LLM for a specific thread."""
    from agent_platform.core.prompts import Prompt
    from agent_platform.core.prompts.messages import PromptTextContent, PromptUserMessage
    from agent_platform.core.responses.content.text import ResponseTextContent
    from agent_platform.server.semantic_data_models.enhancer.prompts import (
        MINIMIZE_REASONING,
        TEMPERATURE,
    )
    from agent_platform.server.semantic_data_models.utils import prompt_generate_internal

    resolved_temperature = TEMPERATURE if temperature is None else temperature
    resolved_minimize_reasoning = MINIMIZE_REASONING if minimize_reasoning is None else minimize_reasoning

    sdm_details = _format_sdm_for_question_prompt(semantic_model)
    system_instruction = SDM_QUESTION_SYSTEM_PROMPT
    user_prompt = f"Semantic Data Model:\n{sdm_details}"

    prompt = Prompt(
        system_instruction=system_instruction,
        messages=[PromptUserMessage(content=[PromptTextContent(text=user_prompt)])],
        temperature=resolved_temperature,
    )
    response = await prompt_generate_internal(
        prompt=prompt,
        user=user,
        storage=storage,
        agent_id=thread.agent_id,
        thread_id=thread.thread_id,
        minimize_reasoning=resolved_minimize_reasoning,
    )
    if not response.content:
        return []

    response_texts = [content.text for content in response.content if isinstance(content, ResponseTextContent)]
    if not response_texts:
        return []

    questions = _parse_sdm_questions_from_llm(response_texts[-1])
    return questions


async def build_sdm_suggested_questions(
    semantic_model: SemanticDataModel,
    model_name: str,
    *,
    user: AuthedUser,
    storage: StorageDependency,
    thread_id: str,
) -> list[str]:
    """Build suggested questions for quick actions."""
    from agent_platform.core.errors import ErrorCode, PlatformHTTPError

    thread = await storage.get_thread(user.user_id, thread_id)
    if thread is None:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message="Thread not found for SDM question generation.",
        )

    questions = await _generate_sdm_questions_via_llm(
        semantic_model=semantic_model,
        user=user,
        storage=storage,
        thread=thread,
    )
    if len(questions) < MIN_SUGGESTED_QUESTIONS:
        raise PlatformHTTPError(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="LLM failed to generate at least 3 suggested questions for the SDM.",
        )
    return questions[:MIN_SUGGESTED_QUESTIONS]


def _build_quick_options_markdown(questions: list[str]) -> str:
    """Render quick options as a markdown code fence for the chat renderer."""
    import json

    payload = {
        "type": "quick-options",
        "data": [
            {"title": f"Question {index}", "message": question} for index, question in enumerate(questions, start=1)
        ],
    }
    return "```sema4-json\n" + json.dumps(payload, indent=2) + "\n```"


async def add_sdm_post_create_messages(
    *,
    storage: StorageDependency,
    user: AuthedUser,
    thread_id: str | None,
    semantic_model: SemanticDataModel,
    semantic_data_model_id: str,
) -> None:
    """Add post-create SDM messages to a thread."""
    import httpx
    from openai import OpenAIError

    from agent_platform.core.errors import PlatformHTTPError
    from agent_platform.core.thread.base import ThreadMessage
    from agent_platform.core.thread.content.text import ThreadTextContent

    if not thread_id or not thread_id.strip():
        return

    model = semantic_model

    sdm_dict = _normalize_sdm_dict(model)
    model_name = sdm_dict.get("name") or "Semantic Data Model"
    summary = build_sdm_post_create_summary(model, model_name)

    quick_options = None
    try:
        questions = await build_sdm_suggested_questions(
            model,
            model_name,
            user=user,
            storage=storage,
            thread_id=thread_id,
        )
        quick_options = _build_quick_options_markdown(questions)
    except (PlatformHTTPError, ValueError, OpenAIError, httpx.HTTPError, TimeoutError) as exc:
        logger.warning(
            "Failed to build SDM suggested questions",
            user_id=user.user_id,
            thread_id=thread_id,
            semantic_data_model_id=semantic_data_model_id,
            exc_info=True,
            error_type=type(exc).__name__,
        )

    agent_text = summary if quick_options is None else f"{summary}\n\n{quick_options}"
    agent_message = ThreadMessage(
        role="agent",
        content=[
            ThreadTextContent(text=agent_text),
        ],
        commited=True,
    )
    agent_message.mark_complete()

    try:
        await storage.add_message_to_thread(user.user_id, thread_id, agent_message)
    except Exception as exc:
        logger.error(
            "Failed to add SDM post-create messages",
            user_id=user.user_id,
            thread_id=thread_id,
            semantic_data_model_id=semantic_data_model_id,
            exc_info=True,
            error_type=type(exc).__name__,
        )
        return

    # Thread existence is already validated in build_sdm_suggested_questions; avoid misleading logs.

    logger.info(
        "Added SDM post-create messages",
        user_id=user.user_id,
        thread_id=thread_id,
        semantic_data_model_id=semantic_data_model_id,
    )
