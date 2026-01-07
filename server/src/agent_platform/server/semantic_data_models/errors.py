"""Custom server-specific error types for semantic data models."""

from agent_platform.core.errors import ErrorCode, PlatformError, PlatformHTTPError


class SemanticDataModelError(PlatformError):
    """Base exception for semantic data model errors."""


class SemanticDataModelWithNameAlreadyExistsError(SemanticDataModelError, PlatformHTTPError):
    """A semantic data model with the given name already exists."""

    def __init__(self, model_name: str):
        message = (
            f"A semantic data model with the name '{model_name}' already exists. "
            f"Semantic data model names must be unique (case-insensitive)"
        )
        super().__init__(error_code=ErrorCode.CONFLICT, message=message)
