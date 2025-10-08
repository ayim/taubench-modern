import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)


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


# Utilities specific to OpenAI retry behaviour.


def _wait_with_retry_after_factory(
    base: float, maximum: float
) -> Callable[[RetryCallState], float]:
    """Return a Tenacity wait function that honors Retry-After header if present."""
    from openai import APIError

    exponential = wait_random_exponential(multiplier=base, max=maximum)

    def _wait(state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        retry_after: float | None = None
        if isinstance(exc, APIError):
            resp = getattr(exc, "response", None)
            headers = getattr(resp, "headers", None) or {}
            retry_after = _parse_retry_after_header(
                headers.get("retry-after") or headers.get("Retry-After")
            )

        return retry_after if retry_after is not None else exponential(state)

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


# Utilities for generic HTTPX-based retries.


def _is_httpx_retryable_factory(retryable_status: set[int]) -> Callable[[BaseException], bool]:
    from httpx import HTTPStatusError, RequestError

    def _predicate(exc: BaseException) -> bool:
        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code
            if status is None:
                return False
            return status in retryable_status or 500 <= status < 600  # noqa: PLR2004
        if isinstance(exc, RequestError):
            return True
        return False

    return _predicate


def _parse_retry_after_header(value: str | None) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        parsed = parsedate_to_datetime(value)
        if parsed is None:
            return None
        retry_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        delay = (retry_dt - datetime.now(UTC)).total_seconds()
        return delay if delay > 0 else None


def _wait_with_httpx_retry_after_factory(
    base: float, maximum: float
) -> Callable[[RetryCallState], float]:
    from httpx import HTTPStatusError

    exponential = wait_random_exponential(multiplier=base, max=maximum)

    def _wait(state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        retry_after: float | None = None
        if isinstance(exc, HTTPStatusError):
            headers = exc.response.headers
            retry_after = _parse_retry_after_header(
                headers.get("retry-after") or headers.get("Retry-After")
            )

        return (
            min(math.ceil(retry_after), maximum) if retry_after is not None else exponential(state)
        )

    return _wait


def _before_sleep_logger_httpx_factory(
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    wait_fn: Callable[[RetryCallState], float],
) -> Callable[[RetryCallState], None]:
    from httpx import HTTPStatusError, RequestError

    def _before_sleep(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        status: int | None = None
        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code
        elif isinstance(exc, RequestError):
            status = None
        delay = state.next_action.sleep if state.next_action else wait_fn(state)
        logger.warning(
            f"{provider_name} {context} retry {state.attempt_number}/{max_attempts - 1} "
            f"after {type(exc).__name__ if exc else 'error'} (status={status}). "
            f"Sleeping {delay:.2f}s."
        )

    return _before_sleep


def _build_httpx_retry_kwargs(  # noqa: PLR0913
    *,
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    base_backoff_s: float,
    max_backoff_s: float,
    retryable_status: set[int],
):
    wait_fn = _wait_with_httpx_retry_after_factory(base_backoff_s, max_backoff_s)
    predicate = _is_httpx_retryable_factory(retryable_status)
    before_sleep = _before_sleep_logger_httpx_factory(
        logger,
        provider_name,
        context,
        max_attempts,
        wait_fn,
    )
    return {
        "retry": retry_if_exception(predicate),
        "stop": stop_after_attempt(max_attempts),
        "wait": wait_fn,
        "reraise": True,
        "before_sleep": before_sleep,
    }


def build_httpx_retry_decorator(  # noqa: PLR0913
    *,
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    base_backoff_s: float,
    max_backoff_s: float,
    retryable_status: set[int],
):
    """Build a Tenacity @retry decorator configured for HTTPX-based APIs."""

    kwargs = _build_httpx_retry_kwargs(
        logger=logger,
        provider_name=provider_name,
        context=context,
        max_attempts=max_attempts,
        base_backoff_s=base_backoff_s,
        max_backoff_s=max_backoff_s,
        retryable_status=retryable_status,
    )

    return retry(**kwargs)


def build_httpx_async_retrying(  # noqa: PLR0913
    *,
    logger: logging.Logger,
    provider_name: str,
    context: str,
    max_attempts: int,
    base_backoff_s: float,
    max_backoff_s: float,
    retryable_status: set[int],
):
    """Build an AsyncRetrying instance configured for HTTPX-based APIs."""

    kwargs = _build_httpx_retry_kwargs(
        logger=logger,
        provider_name=provider_name,
        context=context,
        max_attempts=max_attempts,
        base_backoff_s=base_backoff_s,
        max_backoff_s=max_backoff_s,
        retryable_status=retryable_status,
    )

    return AsyncRetrying(**kwargs)
