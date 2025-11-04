from __future__ import annotations

from typing import TYPE_CHECKING

from agent_platform.core.errors import ErrorCode
from agent_platform.server.semantic_data_models.errors import SemanticDataModelError

if TYPE_CHECKING:
    from agent_platform.core.responses.response import ResponseMessage


class LLMResponseError(SemanticDataModelError):
    """Base exception for LLM response errors that should be retried."""

    def __init__(self, improvement_request: str, response_message: ResponseMessage | None = None):
        self.improvement_request = improvement_request
        self.response_message = response_message
        super().__init__(
            error_code=ErrorCode.UNEXPECTED,
            message=improvement_request,
            data={"response_message": response_message},
        )


class LLMOutputResponseError(LLMResponseError):
    """Raised when LLM returns output response that is not valid."""


class EmptyResponseError(LLMOutputResponseError):
    """Raised when LLM returns empty response."""


class NoToolCallError(LLMOutputResponseError):
    """Raised when LLM response is not empty but is missing tool call."""


class EmptyToolInputError(LLMOutputResponseError):
    """Raised when LLM response contains empty tool input."""


class SchemaValidationError(LLMOutputResponseError):
    """Raised when LLM response doesn't match expected schema."""


# Quality check errors - separate hierarchy with fewer retries
class QualityCheckError(LLMResponseError):
    """Base exception for quality check failures that warrant only 1 retry."""


class EnhancementQualityInsufficientError(QualityCheckError):
    """Raised when LLM's enhancement quality is insufficient."""
