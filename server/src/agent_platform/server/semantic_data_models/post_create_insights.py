"""Helpers for SDM post-create insights and thread messaging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel
from structlog import get_logger
from structlog.stdlib import BoundLogger

if TYPE_CHECKING:
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from agent_platform.core.thread.thread import Thread
    from agent_platform.server.api.dependencies import StorageDependency
    from agent_platform.server.auth import AuthedUser

logger: BoundLogger = get_logger(__name__)


class SDMSuggestedQuestion(BaseModel):
    """A suggested question for an SDM with a title and the full question text."""

    title: str
    question: str


MIN_SUGGESTED_QUESTIONS = 3
MIN_TITLE_WORDS = 3
MAX_TITLE_WORDS = 10
SDM_QUESTION_SYSTEM_PROMPT = (
    "You are a data assistant. Generate three concise natural-language questions "
    "a user can ask about the provided Semantic Data Model. Return ONLY a JSON array "
    "of three objects with keys: title and question. The title must be 3 to 10 words. "
    "Do not include any other text."
)
SDM_SUMMARY_SYSTEM_PROMPT = (
    'Write exactly one sentence starting with: "This model represents". '
    "Use 10 to 20 words. Focus on the data domain and typical analyses. "
    "Do not mention tables or relationships. Return only the sentence."
)


def _normalize_sdm_dict(semantic_model: SemanticDataModel) -> dict:
    """Normalize SDM payload to a dictionary for safe access."""
    return semantic_model.model_dump()


def _normalize_domain_summary(domain_summary: str | None) -> str:
    """Normalize a domain summary to ensure consistent formatting.

    Args:
        domain_summary: The raw domain summary string, or None.

    Returns:
        A normalized summary that:
        - Is stripped of leading/trailing whitespace
        - Ends with a period
        - Starts with "This model represents" (prepended if missing)
        - Returns empty string if input is None or empty
    """
    if not isinstance(domain_summary, str):
        return ""
    normalized = domain_summary.strip()
    if not normalized:
        return ""
    if not normalized.endswith("."):
        normalized = f"{normalized}."
    return normalized


def build_sdm_post_create_summary(
    semantic_model: SemanticDataModel,
    model_name: str,
    domain_summary: str | None,
) -> str:
    """Build a short, deterministic SDM summary for post-create messaging.

    Args:
        semantic_model: The semantic data model payload.
        model_name: The resolved model name to include in the summary.

    Returns:
        A short multi-sentence summary suitable for a chat message.
    """
    table_count = len(semantic_model.tables)
    relationship_count = len(semantic_model.relationships or [])
    schema_count = len(semantic_model.schemas or [])

    table_label = "table" if table_count == 1 else "tables"
    relationship_label = "relationship" if relationship_count == 1 else "relationships"
    schema_label = "schema" if schema_count == 1 else "schemas"

    inclusions = []
    if table_count > 0:
        inclusions.append(f"{table_count} {table_label}")
    if relationship_count > 0:
        inclusions.append(f"{relationship_count} {relationship_label}")
    if schema_count > 0:
        inclusions.append(f"{schema_count} {schema_label}")

    if len(inclusions) <= 2:
        details = " and ".join(inclusions)
    else:
        details = ", ".join(inclusions[:-1]) + ", and " + inclusions[-1]

    normalized_domain_summary = _normalize_domain_summary(domain_summary)

    summary_lines = [
        f'Created a Semantic Data Model called "{model_name}".',
    ]
    if normalized_domain_summary:
        summary_lines.append(normalized_domain_summary)
    summary_lines.append(f"It includes {details}.")
    summary_lines.append("Ask a question about your data.")
    return " ".join(summary_lines)


async def _format_sdm_for_question_prompt(
    semantic_model: SemanticDataModel,
    storage: StorageDependency,
) -> str:
    """Format SDM details into a prompt-friendly string."""
    from agent_platform.server.kernel.semantic_data_model import (
        get_dialect_from_semantic_data_model,
        summarize_data_model,
    )

    # Detect the engine from the semantic data model
    engine = await get_dialect_from_semantic_data_model(semantic_model, storage)
    # Default to duckdb if engine detection fails
    return summarize_data_model(semantic_model, engine or "duckdb")


def _parse_sdm_questions_from_llm(text: str) -> list[SDMSuggestedQuestion]:
    """Parse a JSON array of question entries from the LLM response.

    Args:
        text: The raw LLM response text containing a JSON array.

    Returns:
        A list of validated SDMSuggestedQuestion objects.
    """
    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse SDM questions from LLM output", error="invalid_json")
        return []

    if not isinstance(parsed, list):
        logger.warning("Failed to parse SDM questions from LLM output", error="not_a_list")
        return []

    questions: list[SDMSuggestedQuestion] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        raw_title = item.get("title", "")
        raw_question = item.get("question", "")
        if not isinstance(raw_title, str) or not isinstance(raw_question, str):
            continue
        title = " ".join(raw_title.split())
        question = raw_question.strip()
        if not question:
            continue
        words = title.split()
        if len(words) < MIN_TITLE_WORDS:
            continue
        if len(words) > MAX_TITLE_WORDS:
            title = " ".join(words[:MAX_TITLE_WORDS])
        questions.append(SDMSuggestedQuestion(title=title, question=question))

    return questions


async def _generate_sdm_questions_via_llm(
    *,
    semantic_model: SemanticDataModel,
    user: AuthedUser,
    storage: StorageDependency,
    thread: Thread,
    temperature: float | None = None,
    minimize_reasoning: bool | None = None,
) -> list[SDMSuggestedQuestion]:
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

    sdm_details = await _format_sdm_for_question_prompt(semantic_model, storage)
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

    return _parse_sdm_questions_from_llm(response_texts[-1])


async def _generate_sdm_domain_summary_via_llm(
    *,
    business_context: str,
    user: AuthedUser,
    storage: StorageDependency,
    thread: Thread,
    temperature: float | None = None,
    minimize_reasoning: bool | None = None,
) -> str:
    """Generate a one-sentence domain summary for an SDM via LLM.

    Args:
        business_context: The business context or description of the SDM.
        user: The authenticated user making the request.
        storage: Storage dependency for data access.
        thread: The thread context for the LLM call.
        temperature: Optional temperature override for LLM generation.
        minimize_reasoning: Optional flag to minimize LLM reasoning tokens.

    Returns:
        A single sentence describing the SDM's data domain, or empty string on failure.

    Raises:
        PlatformHTTPError: If thread lookup or LLM call fails.
        OpenAIError: If the underlying LLM provider returns an error.
        httpx.HTTPError: If there's an HTTP communication error.
        TimeoutError: If the LLM call times out.
    """
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
    trimmed_context = business_context.strip()
    user_prompt = f"Business context:\n{trimmed_context}"
    prompt = Prompt(
        system_instruction=SDM_SUMMARY_SYSTEM_PROMPT,
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
        return ""
    response_texts = [content.text for content in response.content if isinstance(content, ResponseTextContent)]
    if not response_texts:
        return ""
    return response_texts[-1].strip()


async def build_sdm_suggested_questions(
    semantic_model: SemanticDataModel,
    model_name: str,
    *,
    user: AuthedUser,
    storage: StorageDependency,
    thread_id: str,
) -> list[SDMSuggestedQuestion]:
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


def _build_quick_options_markdown(questions: list[SDMSuggestedQuestion]) -> str:
    """Render quick options as a markdown code fence for the chat renderer.

    Args:
        questions: List of SDMSuggestedQuestion objects to render.

    Returns:
        A markdown code fence string with JSON payload for the chat renderer.
    """
    import json

    payload = {
        "type": "quick-options",
        "data": [{"title": question.title, "message": question.question} for question in questions],
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
    from agent_platform.core.errors import ErrorCode, PlatformHTTPError
    from agent_platform.core.thread.base import ThreadMessage
    from agent_platform.core.thread.content.text import ThreadTextContent

    if not thread_id or not thread_id.strip():
        return

    model = semantic_model

    sdm_dict = _normalize_sdm_dict(model)
    model_name = sdm_dict.get("name") or "Semantic Data Model"
    domain_summary = ""
    description = sdm_dict.get("description")
    business_context = description if isinstance(description, str) and description.strip() else ""

    try:
        thread = await storage.get_thread(user.user_id, thread_id)
        if thread is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message="Thread not found for SDM summary generation.",
            )
        domain_summary = await _generate_sdm_domain_summary_via_llm(
            business_context=business_context,
            user=user,
            storage=storage,
            thread=thread,
        )
    except Exception as exc:
        logger.warning(
            "Failed to generate SDM summary",
            user_id=user.user_id,
            thread_id=thread_id,
            semantic_data_model_id=semantic_data_model_id,
            exc_info=True,
            error_type=type(exc).__name__,
        )
        domain_summary = ""

    summary = build_sdm_post_create_summary(model, model_name, domain_summary)

    quick_options = None

    # Only generate questions if the SDM has tables.
    if model.tables:
        try:
            questions = await build_sdm_suggested_questions(
                model,
                model_name,
                user=user,
                storage=storage,
                thread_id=thread_id,
            )
            quick_options = _build_quick_options_markdown(questions)
        except Exception as exc:
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
