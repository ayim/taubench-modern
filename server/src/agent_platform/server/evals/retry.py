import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 0.5  # seconds
    backoff_factor: float = 2.0
    max_delay: float = 8.0
    jitter_min: float = 0.0
    jitter_max: float = 0.25


class RetryExceededError(Exception):
    """Raised when retries are exhausted."""

    def __init__(self, message: str, *, last_error: BaseException | None = None) -> None:
        super().__init__(message)
        self.last_error = last_error


async def retry_async(
    op: Callable[[], Awaitable[T]],
    *,
    on_error: Callable[[BaseException, int], None] | None = None,
) -> T:
    """
    Run `op` with retries. Intended for fragile IO/LLM calls or parse/validation steps.
    - `op` must raise on failure (ValueError, JSONDecodeError, etc.)
    - Returns the successful result or raises RetryExceeded.
    """
    attempt = 0
    policy = RetryPolicy()
    delay = policy.initial_delay

    while True:
        try:
            attempt += 1
            return await op()
        except Exception as e:
            if on_error:
                on_error(e, attempt)
            if attempt >= policy.max_attempts:
                raise RetryExceededError(
                    f"Operation failed after {attempt} attempts", last_error=e
                ) from e

            # exponential backoff + jitter
            jitter = random.uniform(policy.jitter_min, policy.jitter_max)
            sleep_for = (
                min(delay * (policy.backoff_factor ** (attempt - 1)), policy.max_delay) + jitter
            )
            logger.debug(
                f"Retrying in {sleep_for:.2f}s "
                f"(attempt {attempt + 1}/{policy.max_attempts}) due to: {e}"
            )
            await asyncio.sleep(sleep_for)
