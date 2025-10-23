import logging

from agent_platform.core.errors.responses import ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)


def log_and_format_error(
    *,
    log_message: str,
    user_message: str,
    error_code: ErrorCode = ErrorCode.UNEXPECTED,
) -> str:
    error_response = ErrorResponse(error_code, message_override=user_message)
    logger.error(f"{log_message} (error_id={error_response.error_id})")
    return f"{error_response.message} (error_id={error_response.error_id})"
