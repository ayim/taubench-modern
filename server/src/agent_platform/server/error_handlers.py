"""Custom error handlers for the FastAPI app including overriding the default handlers.

All handlers in this model should return ORJSONResponse objects that format the error
to match the agreed upon error shape which is:

{
    "error": {
        "code": "family.code",
        "message": "Human readable message to the user."
    }
}
"""

import json
from typing import TYPE_CHECKING, Any

import structlog
from fastapi.exceptions import (
    HTTPException,
    RequestValidationError,
    WebSocketRequestValidationError,
)
from fastapi.requests import Request
from fastapi.responses import ORJSONResponse
from fastapi.utils import is_body_allowed_for_status_code
from fastapi.websockets import WebSocket
from starlette.applications import Starlette
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    WS_1008_POLICY_VIOLATION,
)

from agent_platform.core.errors import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode, ErrorResponse

if TYPE_CHECKING:
    from fastapi.exceptions import ValidationException

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def convert_error_response(
    error_response: ErrorResponse,
    include_message: bool = True,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
) -> ORJSONResponse:
    """Convert an ErrorResponse to a FastAPI Response object.

    Args:
        error_response: The ErrorResponse to convert.
        include_message: Whether to include the message field in the response. If False,
            the default message from the error code will be used.
        status_code: The status code to use for the response. If None, uses the error's status_code.
        headers: The headers to include in the response. Defaults to None.

    Returns:
        A FastAPI ORJSONResponse object.
    """
    # Use the error's status code if not provided
    response_status_code = status_code or error_response.status_code

    out_dict = error_response.model_dump(mode="json")
    if not include_message:
        # Use the default message from the error code
        out_dict["message"] = error_response.error_code.default_message

    if not is_body_allowed_for_status_code(response_status_code):
        return ORJSONResponse(
            status_code=response_status_code,
            headers=headers,
            content={},
        )
    return ORJSONResponse(
        status_code=response_status_code,
        content={"error": out_dict},
        headers=headers,
    )


### Default handlers


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> ORJSONResponse:
    """A custom handler for generic Exception exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.
    """
    error_response = ErrorResponse(ErrorCode.UNEXPECTED, message_override=str(exc))
    _safe_log_error(
        logger.error,
        "Generic Exception (error_id=%s)",
        error_response.error_id,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        exc_info=exc,
    )
    return convert_error_response(
        error_response, include_message=True, status_code=HTTP_500_INTERNAL_SERVER_ERROR
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> ORJSONResponse:
    """A custom handler for generic HTTPException exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.
    """
    # Map HTTP status codes to appropriate ErrorCode values
    status_code_to_error_code = {
        HTTP_400_BAD_REQUEST: ErrorCode.BAD_REQUEST,
        HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
        HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
        HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
        HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
        HTTP_409_CONFLICT: ErrorCode.CONFLICT,
        HTTP_422_UNPROCESSABLE_ENTITY: ErrorCode.UNPROCESSABLE_ENTITY,
        HTTP_429_TOO_MANY_REQUESTS: ErrorCode.TOO_MANY_REQUESTS,
    }

    # Get the error code, defaulting to UNEXPECTED for unmapped status codes
    error_code = status_code_to_error_code.get(exc.status_code, ErrorCode.UNEXPECTED)

    error_response = ErrorResponse(
        error_code, message_override=exc.detail, status_code_override=exc.status_code
    )

    # Do we double log the exception by logging here?
    _safe_log_error(
        logger.error,
        "HTTPException (error_id=%s)",
        error_response.error_id,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        exc_info=exc,
    )
    # Convert Mapping to dict if needed
    headers = dict(exc.headers) if exc.headers is not None else None
    return convert_error_response(error_response, headers=headers)


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> ORJSONResponse:
    """A custom handler for RequestValidationError exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.
    """
    # In prior code, we would check if the exception was a RequestValidationError
    # but per the FastAPI docs and examples, with proper registration, we should not
    # need to do this.

    # Get the pydantic validation error message
    validation_error_message = _format_validation_exception(exc)

    # Create standard error response (ErrorResponse doesn't have a data field)
    error_response = ErrorResponse(
        ErrorCode.UNPROCESSABLE_ENTITY,
        message_override=f"Request validation failed: {validation_error_message}",
    )

    # Redact sensitive data from validation errors and request body before logging
    redacted_validation_errors = _redact_secrets(exc.errors())
    redacted_body = await _get_redacted_request_body(request)

    _safe_log_error(
        logger.error,
        "Request validation failed (error_id=%s): %s",
        error_response.error_id,
        validation_error_message,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        validation_errors=redacted_validation_errors,
        request_body=redacted_body,
    )
    return convert_error_response(error_response)


async def websocket_request_validation_exception_handler(
    websocket: WebSocket,
    exc: WebSocketRequestValidationError,
) -> None:
    """A custom handler for generic WebSocketRequestValidationError exceptions that
    ensures the errors are logged and the response is formatted correctly to match the
    agreed upon error shape.
    """
    # Get the pydantic validation error message
    validation_error_message = _format_validation_exception(exc)

    # Create standard error response (ErrorResponse doesn't have a data field)
    error_response = ErrorResponse(
        ErrorCode.UNPROCESSABLE_ENTITY,
        message_override=f"Request validation failed: {validation_error_message}",
    )

    # Redact sensitive data from validation errors before logging
    # NOTE: WebSocket validation errors don't provide access to the original message body
    # like HTTP requests do, so we can only redact the validation error data itself
    redacted_validation_errors = _redact_secrets(exc.errors())

    _safe_log_error(
        logger.error,
        "WebSocket request validation failed (error_id=%s): %s",
        error_response.error_id,
        validation_error_message,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        validation_errors=redacted_validation_errors,
    )
    # Convert the error response to JSON string for the reason
    error_dict = error_response.model_dump(mode="json")
    await websocket.close(
        code=WS_1008_POLICY_VIOLATION,
        reason=json.dumps({"error": error_dict}),
    )


### Custom handlers for our PlatformError system


async def platform_error_handler(
    request: Request,
    exc: PlatformError,
) -> ORJSONResponse:
    """A custom handler for PlatformError exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.

    This handler returns the underlying error message to allow proper debugging
    and error communication through the API.
    """
    # Log the error with full context using exc_info - the structlog processor
    # will automatically add all the structured error context
    _safe_log_error(
        logger.error,
        "Platform Error (error_id=%s)",
        exc.response.error_id,
        error_id=exc.response.error_id,  # TODO: repeated for current structlog config
        exc_info=exc,
    )
    return convert_error_response(
        exc.response, include_message=True, status_code=HTTP_500_INTERNAL_SERVER_ERROR
    )


async def platform_http_error_handler(
    request: Request,
    exc: PlatformHTTPError,
) -> ORJSONResponse:
    """A custom handler for PlatformHTTPError exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.
    """
    # Log the error with full context using exc_info - the structlog processor
    # will automatically add all the structured error context
    _safe_log_error(
        logger.error,
        "Platform HTTP Error (error_id=%s)",
        exc.response.error_id,
        error_id=exc.response.error_id,  # TODO: repeated for current structlog config
        exc_info=exc,
    )
    return convert_error_response(exc.response, headers=exc.headers)


def add_exception_handlers(app: Starlette) -> None:
    """Adds our custom exception handlers and middleware to the provided FastAPI app."""
    # Override default handlers - use type: ignore to suppress the type checker warnings
    # about handler signatures since FastAPI's type hints are not perfect
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    # Starlette's built-in HTTPException must also be explicitly registered to catch root-level
    # exceptions like 404s and 405s.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        WebSocketRequestValidationError,
        websocket_request_validation_exception_handler,  # type: ignore[arg-type]
    )

    # Add our custom platform error handlers
    # IMPORTANT: Order matters! More specific exceptions must be registered first
    # since PlatformHTTPError inherits from PlatformError, it must be registered first
    app.add_exception_handler(PlatformHTTPError, platform_http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]

    # Generic handler last
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# Internal utilities
# -----------------------------------------------------------------------------


def _format_validation_exception(validation_exc: "ValidationException") -> str:
    """Convert a FastAPI ValidationException into a human-readable string.

    Args:
        validation_exc: The ValidationException to format.

    Returns:
        A human-readable string representation of the validation errors
    """
    try:
        validation_errors = validation_exc.errors()
        # Log the raw validation errors for debugging (temporarily)
        logger.debug("Raw validation errors: %s", validation_errors)

        # Redact sensitive data from validation errors before processing
        redacted_errors = _redact_secrets(validation_errors)
        error_messages = []
        for error in redacted_errors:
            # Convert location tuple to readable path
            if error["loc"]:
                location = " -> ".join(str(part) for part in error["loc"])
                error_messages.append(f"{location}: {error['msg']}")
            else:
                error_messages.append(error["msg"])
        return "; ".join(error_messages)
    except Exception as e:
        logger.debug("Exception formatting validation error: %s", e)
        return "Unknown validation error"


def _safe_log_error(log_method, *args, **kwargs) -> None:
    """Invoke a structlog logging call but swallow *encoding* errors.

    On Windows CI the console encoding can be cp1252 which cannot represent some
    unicode characters emitted by structlog's text renderer (e.g. fancy quotes,
    box-drawing glyphs).  When that happens the *print* call inside structlog
    will raise *UnicodeEncodeError*, which in turn will bubble out of our
    exception handler and incorrectly turn a 4xx/5xx response into an unhandled
    500.

    We never want logging failures to impact request handling, so we trap the
    encoding error here and fall back to a minimal *print* that should always
    succeed.
    """

    try:
        log_method(*args, **kwargs)
    except UnicodeEncodeError as exc:  # pragma: no cover - Windows-only safeguard
        # Emit a very simple ASCII-only fallback; include exc class + message
        # so the information is not completely lost.
        import sys

        safe_msg = (
            f"[logging-failed-encoding] {log_method.__qualname__}: {exc.__class__.__name__}: {exc}"
        )
        print(safe_msg, file=sys.stderr)
        # Do *not* re-raise - we intentionally swallow the failure.


# -----------------------------------------------------------------------------
# Secret redaction utilities
#
# TODO: These utils can likely be moved into structlog config once we are using structlog
# to handle data in the logs. ~ @kylie-bee
# -----------------------------------------------------------------------------


async def _get_redacted_request_body(request: Request) -> str:  # pragma: no cover
    """Get the request body with sensitive data redacted.

    Args:
        request: The FastAPI request object.

    Returns:
        A JSON string of the request body with sensitive fields redacted.
        If the body cannot be parsed as JSON, returns the raw body.
    """
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode()

        # If the body is empty, return empty string
        if not body_str.strip():
            return body_str

        # Try to parse as JSON and redact
        try:
            body_data = json.loads(body_str)
            redacted_data = _redact_secrets(body_data)
            return json.dumps(redacted_data)
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON, return the original body
            # (could be form data, plain text, etc.)
            return body_str
    except Exception:
        # If anything goes wrong, return a safe fallback
        return "[body-redaction-failed]"


def _is_secret_key(key: str) -> bool:  # pragma: no cover
    """Return True if *key* looks like it contains sensitive information.

    This is a **best-effort** heuristic.  When in doubt we err on the side of
    redacting to avoid leaking credentials in logs.
    """

    lowered = key.lower()
    sensitive_fragments = (
        "secret",
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "auth",
        "bearer",
        "key",  # keep last - very generic, checked after more specific fragments
    )
    return any(fragment in lowered for fragment in sensitive_fragments)


def _redact_secrets(value: Any, placeholder: str = "***REDACTED***") -> Any:  # pragma: no cover
    """Recursively traverse *value* (any JSON-serialisable type) and redact secrets.

    Dictionaries have their values replaced with *placeholder* whenever the key
    appears sensitive according to `_is_secret_key`.
    """

    if isinstance(value, dict):
        return {
            k: (placeholder if _is_secret_key(k) else _redact_secrets(v, placeholder))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item, placeholder) for item in value]
    return value
