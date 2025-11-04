"""Custom server-specific error types for semantic data models."""

from agent_platform.core.errors import PlatformError


class SemanticDataModelError(PlatformError):
    """Base exception for semantic data model errors."""
