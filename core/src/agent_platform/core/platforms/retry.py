import logging
import random
from collections.abc import Callable

from tenacity import RetryCallState, retry, retry_if_exception, stop_after_attempt


def _is_openai_retryable_factory(retryable_status: set[int]) -> Callable[[BaseException], bool]:
    """Create a predicate that matches retryable OpenAI exceptions.

    Policy:
    - Always retry connection/timeout errors (transient by nature).
    - Retry on any 5xx except 501 (Not Implemented) and 505 (HTTP Version Not Supported),
      which are typically not transient and won't succeed on retry.
    - Additionally retry on any explicit status codes provided via ``retryable_status``
      (e.g., 408 Request Timeout, 409 Conflict, 429 Too Many Requests).
    """
    from openai import APIConnectionError, APIError, APITimeoutError

    def _predicate(exc: BaseException) -> bool:
        if isinstance(exc, (APITimeoutError | APIConnectionError)):
            return True
        if isinstance(exc, APIError):
            status = getattr(exc, "status_code", None)
            if status is None:
                resp = getattr(exc, "response", None)
                status = getattr(resp, "status_code", None)
            # Retry generic 5xx, excluding clearly non-transient server responses.
            if (
                isinstance(status, int)
                and 500 <= status < 600  # noqa: PLR2004
                and status not in {501, 505}
            ):
                return True
            # Fall back to the explicit allowlist (e.g., 408/409/429).
            return status in retryable_status
        return False

    return _predicate


def _wait_with_retry_after_factory(
    base: float, maximum: float
) -> Callable[[RetryCallState], float]:
    """Return a Tenacity wait function that honors Retry-After header if present.

    Falls back to exponential backoff with jitter when Retry-After is absent.
    """
    from openai import APIError

    def _wait(state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        retry_after: float | None = None
        if isinstance(exc, APIError):
            resp = getattr(exc, "response", None)
            headers = getattr(resp, "headers", None)
            if headers:
                ra = headers.get("retry-after") or headers.get("Retry-After")
                try:
                    retry_after = float(ra) if ra is not None else None
                except Exception:
                    retry_after = None

        attempt = max(1, state.attempt_number)
        base_delay = min(maximum, base * (2 ** (attempt - 1)))
        delay = retry_after if retry_after is not None else base_delay
        return delay * (1 + random.random() * 0.25)  # jitter

    return _wait


def _before_sleep_logger_factory(
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    wait_fn: Callable[[RetryCallState], float],
) -> Callable[[RetryCallState], None]:
    """Return a before-sleep hook that logs attempt, status, and delay."""
    from openai import APIError

    def _before_sleep(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        status: int | None = None
        if isinstance(exc, APIError):
            status = getattr(exc, "status_code", None)
            if status is None:
                resp = getattr(exc, "response", None)
                status = getattr(resp, "status_code", None)
        delay = wait_fn(state)
        logger.warning(
            f"{provider_name} {context} retry {state.attempt_number}/{max_attempts - 1} "
            f"after {type(exc).__name__ if exc else 'error'} "
            f"(status={status}). Sleeping {delay:.2f}s."
        )

    return _before_sleep


def build_openai_retry_decorator(  # noqa: PLR0913
    *,
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    base_backoff_s: float,
    max_backoff_s: float,
    retryable_status: set[int],
):
    """Build a Tenacity @retry decorator configured for OpenAI-like APIs.

    Usage:
        retry_deco = build_openai_retry_decorator(...)

        @retry_deco
        async def _inner():
            return await call()
        await _inner()
    """

    wait_fn = _wait_with_retry_after_factory(base_backoff_s, max_backoff_s)
    before_sleep = _before_sleep_logger_factory(
        logger, provider_name, context, max_attempts, wait_fn
    )
    predicate = _is_openai_retryable_factory(retryable_status)

    return retry(
        retry=retry_if_exception(predicate),
        stop=stop_after_attempt(max_attempts),
        wait=wait_fn,
        reraise=True,
        before_sleep=before_sleep,
    )
