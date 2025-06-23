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
    body = (await request.body()).decode()

    # Create standard error response (ErrorResponse doesn't have a data field)
    error_response = ErrorResponse(ErrorCode.UNPROCESSABLE_ENTITY)

    _safe_log_error(
        logger.error,
        "Request validation failed (error_id=%s)",
        error_response.error_id,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        validation_errors=exc.errors(),
        request_body=body,
        exc_info=exc,
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
    # Create standard error response (ErrorResponse doesn't have a data field)
    error_response = ErrorResponse(ErrorCode.UNPROCESSABLE_ENTITY)

    _safe_log_error(
        logger.error,
        "WebSocket request validation failed (error_id=%s)",
        error_response.error_id,
        error_id=error_response.error_id,  # TODO: repeated for current structlog config
        validation_errors=exc.errors(),
        exc_info=exc,
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

    IMPORTANT: PlatformError instances are considered INTERNAL ERRORS and should NOT
    expose sensitive information to clients. This handler returns a generic 500 error
    with minimal information to protect internal system details.
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
        exc.response, include_message=False, status_code=HTTP_500_INTERNAL_SERVER_ERROR
    )


async def platform_http_error_handler(
    request: Request,
    exc: PlatformHTTPError,
) -> ORJSONResponse:
    """A custom handler for PlatformHTTPError exceptions that ensures the errors are
    logged and the response is formatted correctly to match the agreed upon error shape.

    PlatformHTTPError instances may expose information to clients, so this handler
    uses the error's status code and may include the error message and data.
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
    """Adds our custom exception handlers to the provided FastAPI app."""
    # Override default handlers - use type: ignore to suppress the type checker warnings
    # about handler signatures since FastAPI's type hints are not perfect
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
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


# -----------------------------------------------------------------------------
# Internal utilities
# -----------------------------------------------------------------------------


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
