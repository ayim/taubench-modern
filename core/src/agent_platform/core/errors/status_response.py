"""Status-based response models for endpoints that always return 200 OK.

This module provides response models for endpoints that need to return success/failure
status in the response body rather than using HTTP status codes. This pattern is useful
for operations that may partially succeed or when you want consistent 200 OK responses
regardless of the outcome.

Example usage:
```python
@router.post("/inspect/action")
async def inspect_action_from_package(...) -> StatusResponse[ActionMetadata]:
    try:
        result = perform_inspection(...)
        return StatusResponse.success(result)
    except PlatformError as pe:
        return StatusResponse.failure([StatusError.from_platform_error(pe)])
    except Exception as e:
        logger.exception("Inspection failed")
        return StatusResponse.failure([StatusError.from_message("Failed to inspect package")])
```
"""

from collections.abc import Sequence
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

# Generic type for the data payload
T = TypeVar("T")


class StatusError(BaseModel):
    """A client-safe error representation that can be included in StatusResponse.

    This model extracts safe information from PlatformError objects while
    excluding sensitive internal details.
    """

    code: str = Field(description="Error code identifying the type of error")
    message: str = Field(description="Human-readable error message")
    error_id: str | None = Field(default=None, description="Unique error identifier for tracking")

    @classmethod
    def from_platform_error(cls, platform_error) -> "StatusError":
        """Create a StatusError from a PlatformError, exposing only safe information.

        Args:
            platform_error: A PlatformError instance

        Returns:
            StatusError with safe error information
        """
        # Import here to avoid circular imports
        from agent_platform.core.errors.base import PlatformError

        if not isinstance(platform_error, PlatformError):
            raise TypeError("Expected PlatformError instance")

        return cls(
            code=platform_error.response.code,
            message=platform_error.response.message,
            error_id=str(platform_error.response.error_id),
        )

    @classmethod
    def from_message(cls, message: str, code: str = "unexpected") -> "StatusError":
        """Create a StatusError from a simple error message.

        Args:
            message: The error message
            code: Optional error code, defaults to "unexpected"

        Returns:
            StatusError with the provided message and code
        """
        return cls(code=code, message=message, error_id=None)


class StatusResponse(BaseModel, Generic[T]):
    """A response model that always returns 200 OK but includes status in the body.

    This model provides a consistent structure for endpoints that need to return
    both success and failure cases without using HTTP error status codes.
    """

    status: Literal["success", "failure"] = Field(
        description="Indicates whether the operation was successful"
    )

    data: T | None = Field(
        default=None, description="The result data when successful, null when failed"
    )

    errors: list[StatusError | str] = Field(
        default_factory=list, description="List of errors when the operation fails"
    )

    @classmethod
    def success(cls, data: T) -> "StatusResponse[T]":
        """Create a successful response with data.

        Args:
            data: The successful operation result

        Returns:
            StatusResponse with status="success" and the provided data
        """
        return cls(status="success", data=data, errors=[])

    @classmethod
    def failure(cls, errors: Sequence[StatusError | str]) -> "StatusResponse[T]":
        """Create a failure response with error information.

        Args:
            errors: List of errors (StatusError objects or string messages)

        Returns:
            StatusResponse with status="failure" and the provided errors
        """
        return cls(status="failure", data=None, errors=list(errors))

    @classmethod
    def failure_from_platform_errors(cls, platform_errors: Sequence) -> "StatusResponse[T]":
        """Create a failure response from PlatformError instances.

        Args:
            platform_errors: List of PlatformError instances

        Returns:
            StatusResponse with status="failure" and safe error information
        """
        status_errors: list[StatusError | str] = [
            StatusError.from_platform_error(pe) for pe in platform_errors
        ]
        return cls(status="failure", data=None, errors=status_errors)

    @classmethod
    def failure_from_messages(cls, messages: Sequence[str]) -> "StatusResponse[T]":
        """Create a failure response from error messages.

        Args:
            messages: List of error message strings

        Returns:
            StatusResponse with status="failure" and the provided messages as strings
        """
        return cls(status="failure", data=None, errors=list(messages))

    @property
    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.status == "success"

    @property
    def is_failure(self) -> bool:
        """Check if the response indicates failure."""
        return self.status == "failure"
