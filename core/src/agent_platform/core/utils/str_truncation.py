from collections.abc import Callable

from agent_platform.core.prompts import PromptTextContent


def _max_words_within_token_limit(
    words: list[str],
    max_tokens: int,
    counter: Callable[[str], int],
) -> str:
    """Binary search the largest prefix of ``words`` within ``max_tokens``."""
    low, high = 0, len(words)
    best = ""

    while low < high:
        mid = (low + high + 1) // 2
        candidate = " ".join(words[:mid]).strip()
        if not candidate:
            high = mid - 1
            continue
        if counter(candidate) <= max_tokens:
            best = candidate
            low = mid
        else:
            high = mid - 1

    if not best and words:
        first = words[0].strip()
        if first and counter(first) <= max_tokens:
            best = first

    if best and counter(best) <= max_tokens:
        return best
    return ""


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate to ``max_chars`` at a sensible word boundary when possible.

    Args:
        text: The text to truncate
        max_chars: The maximum number of characters to keep

    Returns:
        The truncated text
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rstrip()
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.6:
        truncated = truncated[:last_space]
    return truncated


def truncate_text_by_tokens(text: str | None, max_tokens: int) -> str:
    """Truncate text to a token budget using the project's tokenizer.

    Args:
        text: The text to truncate
        max_tokens: The maximum number of tokens to keep

    Returns:
        The truncated text
    """
    if not text:
        return ""

    counter = PromptTextContent.count_tokens_in_text
    if counter(text) <= max_tokens:
        return text

    words = text.split()
    if not words:
        return ""

    best = _max_words_within_token_limit(words, max_tokens, counter)
    if not best:
        return ""

    if best == text:
        return best

    return f"{best}..."
