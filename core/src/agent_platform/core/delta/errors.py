"""Error types for delta operations."""

from typing import Literal

from agent_platform.core.delta.base import GenericDelta


class DeltaError(Exception):
    """Base class for all delta-related errors."""

    delta_object: GenericDelta | None = None
    """The delta object that caused the error."""

    def __init__(self, message: str, delta_object: GenericDelta | None = None):
        super().__init__(message)
        self.delta_object = delta_object


class InvalidPathError(DeltaError):
    """Raised when a path in a delta operation is invalid or cannot be resolved."""

    def __init__(
        self,
        path: str,
        path_attr: Literal["path", "from_"] = "path",
        message: str | None = None,
        detailed_message: str | None = None,
        delta_object: GenericDelta | None = None,
    ) -> None:
        self.path = path
        self.path_attr = path_attr
        super().__init__(
            message
            or (f"Invalid target path '{path}'" if path_attr == "path" else f"Invalid source path '{path}'")
            + (f": {detailed_message}" if detailed_message else ""),
            delta_object=delta_object,
        )


class InvalidOperationError(DeltaError):
    """Raised when an invalid or unsupported delta operation is attempted."""

    def __init__(
        self,
        operation: str,
        message: str | None = None,
        delta_object: GenericDelta | None = None,
    ) -> None:
        self.operation = operation
        super().__init__(
            message or f"Invalid operation '{operation}' - operation not supported",
            delta_object=delta_object,
        )
