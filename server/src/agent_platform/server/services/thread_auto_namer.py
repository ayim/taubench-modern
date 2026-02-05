import re
from asyncio import CancelledError
from datetime import UTC, datetime

import structlog

from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.thread import Thread
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.utils.str_truncation import truncate_text, truncate_text_by_tokens
from agent_platform.server.kernel import AgentServerKernel
from agent_platform.server.storage import BaseStorage, ThreadNotFoundError

logger = structlog.get_logger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are naming a chat thread. Generate a concise, descriptive title based on the user's "
    "first message and brief agent context. Constraints: 3-12 words, Title Case, no quotes, no "
    "code blocks, no trailing punctuation. Emit only the name, no other text."
)
_MAX_AGENT_DESCRIPTION_TOKENS = 1000
_MAX_RUNBOOK_TOKENS = 32_000
_MAX_USER_MESSAGE_TOKENS = 16_000
_MAX_NAME_LENGTH = 80
# Allow unicode letters/digits/underscore via \w, plus space and hyphen. Strip everything else.
_ALLOWED_NAME_PATTERN = re.compile(r"[^\w \-]+", re.UNICODE)


async def maybe_auto_name_thread(kernel: AgentServerKernel, storage: BaseStorage) -> str | None:
    """Best-effort asynchronous auto-naming.

    Attempts to auto-name the current thread if eligible. Errors are logged and
    never allowed to crash the caller; cancellations are propagated.

    Returns:
        The new thread name if auto-naming succeeded, None otherwise.
    """

    try:
        return await _maybe_auto_name_thread(kernel, storage)
    except CancelledError:
        logger.debug(
            f"Auto naming task cancelled for thread ({kernel.thread.thread_id})  | run ({kernel.run.run_id})",
        )
        raise
    except Exception:
        logger.exception(
            f"Auto naming task failed for thread ({kernel.thread.thread_id})  | run ({kernel.run.run_id})",
        )
        return None


async def _maybe_auto_name_thread(kernel: AgentServerKernel, storage: BaseStorage) -> str | None:
    """Core auto-naming flow guarded by eligibility checks.

    Returns:
        The new thread name if auto-naming succeeded, None otherwise.
    """
    thread_id = kernel.thread.thread_id
    agent_id = kernel.agent.agent_id
    current_run_id = kernel.run.run_id

    # Never rename for worker agents
    if kernel.agent.is_worker_agent():
        return None

    if not _check_thread_eligibility(kernel.thread):
        return None

    if not await _is_first_run_for_thread(storage, thread_id, current_run_id, agent_id):
        return None

    first_user_message = _extract_first_user_message(kernel.thread)
    if not first_user_message:
        logger.debug(
            f"Skipping auto naming because no user message found for thread ({thread_id})",
        )
        return None

    name_and_model = await _generate_thread_name(
        kernel,
        kernel.thread,
        first_user_message,
    )
    if not name_and_model:
        return None

    name, model = name_and_model

    await _persist_auto_named_thread(
        kernel,
        storage,
        kernel.thread,
        name,
        model,
    )
    return name


def _check_thread_eligibility(
    thread: Thread,
) -> bool:
    """Return ``True`` when the thread is eligible for auto-naming."""
    if thread.is_associated_with_workitem():
        logger.debug(
            f"Skipping auto naming for work item thread ({thread.thread_id})",
        )
        return False

    if thread.auto_naming_disabled():
        logger.debug(
            f"Auto naming disabled via metadata for thread ({thread.thread_id})",
        )
        return False

    if thread.is_user_named():
        logger.debug(
            f"Thread already manually named by user for thread ({thread.thread_id})",
        )
        return False

    if thread.has_been_auto_named():
        logger.debug(
            f"Thread already auto named previously for thread ({thread.thread_id})",
        )
        return False

    return True


async def _is_first_run_for_thread(storage: BaseStorage, thread_id: str, current_run_id: str, agent_id: str) -> bool:
    """True if the current run is the thread's first run."""
    runs = await storage.list_runs_for_thread(thread_id)
    for run in runs:
        if run.run_id != current_run_id:
            logger.debug(
                f"Skipping auto naming because prior runs exist for thread ({thread_id})",
            )
            return False
    return True


async def _generate_thread_name(
    kernel: AgentServerKernel,
    thread: Thread,
    first_user_message: str,
) -> tuple[str, str] | None:
    """Generate and sanitize a thread name using the selected LLM.

    Returns a tuple of ``(name, model_id)`` on success, or ``None`` if name
    generation fails. Names are sanitized but not forced to be unique.
    """
    prompt = _build_prompt(
        first_user_message,
        kernel.agent.name,
        kernel.agent.description,
        kernel.agent.runbook_structured.raw_text,
    )

    try:
        platform, model = await kernel.get_platform_and_model(model_type="llm")
    except Exception:
        logger.exception(
            f"Unable to select model for auto naming for thread ({thread.thread_id})",
            exc_info=True,
        )
        return None

    try:
        response = await platform.generate_response(prompt, model)
    except Exception:
        logger.exception(
            f"Failed to generate auto name for thread ({thread.thread_id})",
            exc_info=True,
        )
        return None

    generated_name = _extract_response_text(response)
    sanitized_name = _sanitize_name(generated_name)
    if not sanitized_name:
        logger.debug(
            f"Generated name was empty after sanitization for thread ({thread.thread_id})",
        )
        return None

    return sanitized_name, model


async def _persist_auto_named_thread(
    kernel: AgentServerKernel,
    storage: BaseStorage,
    original_thread: Thread,
    name: str,
    model: str,
) -> None:
    """Persist the new name if the thread hasn't changed underneath us."""
    agent_id = original_thread.agent_id
    try:
        latest_thread = await storage.get_thread(kernel.user.user_id, original_thread.thread_id)
    except ThreadNotFoundError:
        logger.debug(
            f"Thread disappeared before auto naming could be applied for thread ({original_thread.thread_id})",
            exc_info=True,
        )
        return

    latest_meta = latest_thread.metadata.get("thread_name", {})
    if latest_thread.is_user_named():
        logger.debug(
            f"User renamed thread before auto naming could be applied for thread ({original_thread.thread_id})",
        )
        return

    if latest_thread.name != original_thread.name:
        logger.debug(
            f"Thread name changed before auto naming could be applied for thread ({original_thread.thread_id})",
        )
        return

    now_iso = datetime.now(UTC).isoformat()
    if "original_name" not in latest_meta:
        latest_meta["original_name"] = latest_thread.name
        latest_meta["original_name_at"] = now_iso
    latest_meta["auto_named_at"] = now_iso

    previous_name = latest_thread.name
    latest_thread.name = name
    latest_thread.metadata = {
        **latest_thread.metadata,
        "thread_name": latest_meta,
    }
    latest_thread.updated_at = datetime.now(UTC)

    await storage.upsert_thread(kernel.user.user_id, latest_thread)

    logger.info(
        f"Thread ({original_thread.thread_id}) auto named successfully: {name} ({model})",
    )

    # Best-effort notify clients over the kernel's outgoing events
    try:
        from agent_platform.core.streaming.delta import StreamingDeltaThreadNameUpdated

        await kernel.outgoing_events.dispatch(
            StreamingDeltaThreadNameUpdated(
                timestamp=datetime.now(UTC),
                thread_id=original_thread.thread_id,
                agent_id=agent_id,
                new_name=name,
                old_name=previous_name,
                reason="auto",
            ),
        )
    except Exception:
        # Do not propagate errors from event dispatch
        logger.debug(
            f"Failed to dispatch thread rename event for thread ({original_thread.thread_id})",
            exc_info=True,
        )


def _extract_first_user_message(thread: Thread) -> str | None:
    """Extract the first user's textual message, normalized and truncated.

    Merges multiple ``ThreadTextContent`` parts for the first user message,
    collapses whitespace, and truncates by token limit for prompt construction.
    Returns ``None`` if no user message is present.
    """
    for message in thread.messages:
        if message.role != "user":
            continue
        text_parts: list[str] = []
        for content in message.content:
            if isinstance(content, ThreadTextContent):
                text_parts.append(content.text.strip())
        if text_parts:
            text = " ".join(text_parts)
            return truncate_text_by_tokens(text.strip(), _MAX_USER_MESSAGE_TOKENS)
    return None


def _build_prompt(
    user_message: str,
    agent_name: str | None,
    agent_description: str | None,
    runbook_text: str | None,
) -> Prompt:
    """Build the instruction and user content for naming prompt."""
    sections: list[str] = []

    if agent_name:
        sections.append(f"Agent name: {agent_name}")

    description_excerpt = truncate_text_by_tokens(
        agent_description,
        _MAX_AGENT_DESCRIPTION_TOKENS,
    )
    if description_excerpt:
        sections.append(f"Agent description: {description_excerpt}")

    runbook_excerpt = truncate_text_by_tokens(
        runbook_text,
        _MAX_RUNBOOK_TOKENS,
    )
    if runbook_excerpt:
        sections.append(f"Agent runbook (excerpt): {runbook_excerpt}")

    sections.append(f"User's first message: {user_message}")

    user_content = "\n".join(sections)
    return Prompt(
        system_instruction=_SYSTEM_INSTRUCTION,
        messages=[PromptUserMessage(content=[PromptTextContent(text=user_content)])],
        temperature=0.60,
        # For reasoning models... we can't set this as low as you'd think
        # else we chop reasoning and get no output; so let's set it high, modern
        # models should be fine w/out a _strict_ token limit at a "generate short name"
        # task
        max_output_tokens=4096,
        top_p=1.0,
        minimize_reasoning=True,
    )


def _extract_response_text(response: ResponseMessage) -> str | None:
    """Join text parts from the LLM response and normalize whitespace."""
    text_fragments = [content.text for content in response.content if isinstance(content, ResponseTextContent)]
    if not text_fragments:
        return None
    return " ".join(text_fragments)


def _sanitize_name(name: str | None) -> str | None:
    r"""Normalize and restrict a proposed thread name.

    - Collapses all whitespace to single spaces and trims ends.
    - Strips surrounding quotes/backticks (straight and curly).
    - Removes newlines and leading/trailing punctuation/spaces.
    - Removes any disallowed characters (allows ``\w``, space, and ``-``).
    - Truncates to ``_MAX_NAME_LENGTH`` characters, attempting to break on a word boundary.

    Returns ``None`` if the result becomes empty.
    Note: This does not enforce Title Case; the LLM is prompted to produce it.
    """
    if not name:
        return None
    cleaned = name.strip()
    cleaned = cleaned.strip("\"'`\u201c\u201d\u2018\u2019")
    cleaned = re.sub(r"[\s]+", " ", cleaned)
    cleaned = cleaned.strip(" .!?:;,-")
    cleaned = _ALLOWED_NAME_PATTERN.sub("", cleaned)
    if not cleaned:
        return None
    if len(cleaned) > _MAX_NAME_LENGTH:
        cleaned = truncate_text(cleaned, _MAX_NAME_LENGTH)
    return cleaned.strip()
