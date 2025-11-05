"""Strongly typed error responses for all error objects sent to frontend."""

import json
import uuid
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Any, Literal, NamedTuple

from fastapi.encoders import jsonable_encoder


class ErrorInfo(NamedTuple):
    """Information about an error type."""

    code: str
    default_message: str
    default_status_code: int


class ErrorCode(Enum):
    """The base error code which can be used to identify and begin to debug the error."""

    UNEXPECTED = ErrorInfo("unexpected", "An unexpected error occurred.", 500)
    BAD_REQUEST = ErrorInfo(
        "bad_request",
        "The request was invalid. Please check the request and try again.",
        400,
    )
    UNPROCESSABLE_ENTITY = ErrorInfo(
        "unprocessable_entity",
        "Request validation failed. Please check the request and try again.",
        422,
    )
    UNAUTHORIZED = ErrorInfo(
        "unauthorized",
        "You are not authorized to access this resource.",
        401,
    )
    NOT_FOUND = ErrorInfo(
        "not_found",
        "The requested resource was not found.",
        404,
    )
    FORBIDDEN = ErrorInfo(
        "forbidden",
        "You do not have permission to access this resource.",
        403,
    )
    CONFLICT = ErrorInfo(
        "conflict",
        "The request conflicts with an existing resource.",
        409,
    )
    METHOD_NOT_ALLOWED = ErrorInfo(
        "method_not_allowed",
        "The requested method is not allowed for this resource.",
        405,
    )
    TOO_MANY_REQUESTS = ErrorInfo(
        "too_many_requests",
        "Too many requests. Please try again later.",
        429,
    )
    PRECONDITION_FAILED = ErrorInfo(
        "precondition_failed",
        "The request failed due to a invalid state.",
        412,
    )
    INTERNAL_ERROR = ErrorInfo(
        "internal_error",
        "An internal error occurred while processing this request.",
        500,
    )

    @property
    def code(self) -> str:
        """Get the error code string."""
        return self.value.code

    @property
    def default_message(self) -> str:
        """Get the default error message."""
        return self.value.default_message

    @property
    def default_status_code(self) -> int:
        """Get the HTTP status code."""
        return self.value.default_status_code


@dataclass
class ErrorResponse:
    """The representation of errors sent via the API to the client."""

    error_code: ErrorCode

    # InitVar fields - used for initialization but not stored as fields
    message_override: InitVar[str | None] = None
    status_code_override: InitVar[int | None] = None

    # Actual fields with correct non-None types
    message: str = field(init=False)
    status_code: int = field(init=False)
    error_id: uuid.UUID = field(
        default_factory=uuid.uuid4,
        init=False,
        metadata={
            "description": "A unique identifier for the error for tracing from frontend "
            "to logs and other services."
        },
    )

    # TODO: in the future we should consider additional fields here like
    # customer_facing_message, llm_prompt_debug_message, etc.

    def __post_init__(self, message_override: str | None, status_code_override: int | None) -> None:
        """Set message and status code from overrides or defaults."""
        self.message = message_override or self.error_code.default_message
        self.status_code = status_code_override or self.error_code.default_status_code

    @property
    def code(self) -> str:
        """Get the error code string."""
        return self.error_code.code

    def model_dump(self, mode: Literal["json", "python"] = "python") -> dict[str, Any]:
        """Convert ErrorResponse to a dictionary for serialization."""
        out_dict = {
            "error_id": str(self.error_id),
            "code": self.code,
            "message": self.message,
        }
        if mode == "json":
            return jsonable_encoder(out_dict)
        return out_dict

    def model_dump_json(self) -> str:
        """Convert ErrorResponse to a JSON string for serialization."""
        return json.dumps(self.model_dump(mode="json"))
