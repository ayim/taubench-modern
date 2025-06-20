"""Platform error system with automatic structured logging integration.

This module defines a hierarchy of exception classes designed to work seamlessly with
FastAPI and structlog for rich, structured error logging and handling.

## Architecture Overview

The error system provides:
- Automatic unique error IDs (UUIDs) for tracing
- Structured context data that integrates with structlog (full integration coming)
- FastAPI-compatible HTTP and WebSocket exceptions
- Centralized API error response formatting through ErrorResponse classes

## Usage Patterns

### Basic Usage
```python
# Simple error with message and structured data
raise PlatformError(
    ErrorCode.UNEXPECTED,
    "Configuration validation failed",
    data={"config_key": "database_url", "validation_error": "invalid format"}
)

# HTTP error for API endpoints
raise PlatformHTTPError(
    ErrorCode.UNAUTHORIZED,
    # String interpolation is coming soon after structlog is fully integrated
    f"User {user_id} not authorized for this resource",
    data={"user_id": user_id, "resource": "admin_panel"}
)

# WebSocket error
raise PlatformWebSocketError(
    ErrorCode.BAD_REQUEST,
    # String interpolation is coming soon after structlog is fully integrated
    f"Invalid message format received: {msg_type}",
    data={"message_type": msg_type, "expected_fields": ["id", "action"]},
    close_code=1003
)
```

> Note: Be careful what data you put in the string as the message may be sent to the clients and
> be exposed to end users who may not understand the context.

### Exception Handling
```python
try:
    # Some operation that might fail
    result = dangerous_operation()
except SomeExternalError as e:
    # Wrap external errors with context
    raise PlatformError(
        ErrorCode.UNEXPECTED,
        "External service failed",
        data={
            "service": "payment_processor",
            "original_error": str(e),
            "retry_count": retry_count
        }
    ) from e
```

## Error Response System

Each error class uses an `ErrorResponse` class to provide consistent structure:
- Automatic UUID generation for error tracking
- Consistent field naming and JSON serialization
- Integration with FastAPI for client responses
- Structured logging context generation

## Error Tracing

Each error instance gets a unique `error_id` UUID. This allows you to:
- Correlate the same error across multiple log entries
- Track error propagation through your system
- Search logs for all occurrences of a specific error instance
- Debug distributed systems by following error IDs across services

Example log output:
```log
2025-06-19 13:47:41,481 - agent_platform.server.agent_architectures.in_process_runner -
  ERROR:    Error during agent architecture invocation
  (error_id=27df921d-3079-4306-86e3-74013eda8aef)
Traceback (most recent call last):
  File ...
```
"""

from typing import Any

import structlog
from starlette.status import WS_1011_INTERNAL_ERROR

from agent_platform.core.errors.responses import ErrorCode, ErrorResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlatformError(Exception):
    """Base class for platform errors. All errors originating from our platform should
    inherit from this class.

    IMPORTANT: PlatformError instances are considered INTERNAL ERRORS. The error message
    and data will NOT be exposed to clients - they are only used for internal logging
    and debugging. This makes PlatformError safe for including sensitive information
    in the data field.

    Use this class when:
    - The error represents an internal system failure
    - You need to include sensitive debugging information
    - The error should not be directly visible to API clients

    For errors that should be returned to HTTP clients, use PlatformHTTPError instead.
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.UNEXPECTED,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a platform error.

        Args:
            error_code: The error code enum that defines the error type.
            message: Optional custom error message. If not provided, uses the default
                from error_code.
            data: Optional data associated with the error for structured logging.
        """
        self.response = ErrorResponse(error_code, message_override=message)
        self.data = data or {}
        super().__init__(self.response.message)

    def __str__(self) -> str:
        """Return a formatted string representation of the error."""
        return self.response.message

    def __repr__(self) -> str:
        """Return a string representation of the error."""
        # Do not attempt to stringify data
        return (
            f"{self.__class__.__name__}(code={self.response.code!r}, "
            f"message={self.response.message!r}, "
            f"error_id={self.response.error_id!r})"
        )

    def to_log_context(self) -> dict[str, Any]:
        """Convert error to structured log context.

        Returns:
            Dictionary suitable for structlog context with JSON-serializable values.
        """
        # Let structlog handle serializing data, which may simply be to use __repr__
        return {"error": self.response.model_dump(mode="json"), **self.data}


class PlatformHTTPError(PlatformError):
    """Base class for platform HTTP errors.

    IMPORTANT: PlatformHTTPError instances MAY be exposed to HTTP clients depending
    on the status code and your FastAPI exception handlers. The error message and
    potentially the data field could be visible to clients.

    Use this class when:
    - The error should be returned as an HTTP response
    - You want FastAPI to automatically use the status_code
    - The error information is safe to potentially expose to clients

    SECURITY NOTE: Be careful about including sensitive information in the message
    or data fields, as these may be sent to clients depending on your exception
    handling configuration and the HTTP status code.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize a platform HTTP error.

        Args:
            error_code: The error code enum that defines the error type.
            message: Optional custom error message. If not provided, uses the default
                from error_code.
            data: Optional data associated with the error.
            status_code: Optional HTTP status code override. If not provided, uses the
                default from error_code.
            headers: Optional HTTP headers.
        """
        # Create response with status code override if provided
        self.response = ErrorResponse(
            error_code, message_override=message, status_code_override=status_code
        )
        self.data = data or {}

        # HTTP-specific attributes that FastAPI can use
        self.status_code = self.response.status_code
        self.detail = self.response.message
        self.headers = headers

        # Initialize the exception with the message
        Exception.__init__(self, self.response.message)

    def to_log_context(self) -> dict[str, Any]:
        """Convert HTTP error to structured log context."""
        context = super().to_log_context()
        # Add HTTP-specific fields to the top level context
        context["status_code"] = self.status_code
        if self.headers:
            context["headers"] = dict(self.headers)
        return context


class PlatformWebSocketError(PlatformError):
    """Base class for platform WebSocket errors.

    IMPORTANT: PlatformWebSocketError instances MAY be exposed to WebSocket clients
    depending on your WebSocket exception handling. The error message and close
    reason could be visible to clients.

    Use this class when:
    - The error should close a WebSocket connection
    - You want to send a specific close code to the client
    - The error information is safe to potentially expose to clients

    SECURITY NOTE: Be careful about including sensitive information in the message,
    reason, or data fields, as these may be sent to clients depending on your
    WebSocket exception handling configuration.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        close_code: int = WS_1011_INTERNAL_ERROR,
        reason: str | None = None,
    ) -> None:
        """Initialize a platform WebSocket error.

        Args:
            error_code: The error code enum that defines the error type.
            message: Optional custom error message. If not provided, uses the default
                from error_code.
            data: Optional data associated with the error.
            close_code: The WebSocket close code.
            reason: Optional close reason, if not provided, the message will be used.
        """
        super().__init__(error_code=error_code, message=message, data=data)

        # WebSocket-specific attributes
        self.close_code = close_code
        self.reason = reason or self.response.message

    def to_log_context(self) -> dict[str, Any]:
        """Convert WebSocket error to structured log context."""
        context = super().to_log_context()

        # Add WebSocket-specific fields to the top level context
        context["websocket_close_code"] = self.close_code
        context["websocket_reason"] = self.reason
        return context
