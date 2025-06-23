"""Errors that are raised during agent architecture invocation/streaming."""

from typing import Any

from starlette.status import WS_1008_POLICY_VIOLATION, WS_1011_INTERNAL_ERROR

from agent_platform.core.errors.base import PlatformWebSocketError
from agent_platform.core.errors.responses import ErrorCode


class StreamingError(PlatformWebSocketError):
    """Base class for streaming errors."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.UNEXPECTED,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        close_code: int = WS_1011_INTERNAL_ERROR,
        reason: str | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            data=data,
            close_code=close_code,
            reason=reason,
        )


class StreamingKernelError(StreamingError):
    """An error raised from the kernel during agent architecture invocation/streaming."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.UNEXPECTED,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        close_code: int = WS_1011_INTERNAL_ERROR,
        reason: str | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            data=data,
            close_code=close_code,
            reason=reason,
        )


class NoPlatformOrModelFoundError(StreamingKernelError):
    """An error raised when no platform or model can be found based on the requested parameters."""

    def __init__(
        self,
        message: str | None = "No platform or model found for the requested parameters.",
        data: dict[str, Any] | None = None,
        close_code: int = WS_1008_POLICY_VIOLATION,
        reason: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            message=message,
            data=data,
            close_code=close_code,
            reason=reason,
        )
