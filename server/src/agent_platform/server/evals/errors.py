import logging
from typing import Any

from agent_platform.core.errors.responses import ErrorCode, ErrorResponse
from agent_platform.core.errors.streaming import StreamingError

logger = logging.getLogger(__name__)


class TrialRateLimitedError(Exception):
    """Signal that a trial hit rate limits and should be retried."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def is_rate_limit_error(exc: BaseException) -> bool:
    if isinstance(exc, StreamingError):
        return exc.response.error_code == ErrorCode.TOO_MANY_REQUESTS
    return False


def retry_after_from_exception(exc: BaseException) -> float | None:
    data: dict[str, Any] | None = None
    if isinstance(exc, StreamingError):
        data = getattr(exc, "data", None)

    if not isinstance(data, dict):
        return None
    value = data.get("retry_after_seconds")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def log_and_format_error(
    *,
    log_message: str,
    user_message: str,
    error_code: ErrorCode = ErrorCode.UNEXPECTED,
) -> str:
    error_response = ErrorResponse(error_code, message_override=user_message)
    logger.error(f"{log_message} (error_id={error_response.error_id})")
    return f"{error_response.message} (error_id={error_response.error_id})"
