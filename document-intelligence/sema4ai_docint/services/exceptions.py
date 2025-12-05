"""
Custom exceptions for document intelligence services.
"""

from sema4ai.actions import ActionError


class DocumentServiceError(ActionError):
    """Base exception for document service operations."""

    pass


class LayoutServiceError(ActionError):
    """Exception for document layout operations."""

    pass


class DataModelServiceError(ActionError):
    """Exception for data model operations."""

    pass


class ExtractionServiceError(ActionError):
    """Exception for extraction operations."""

    pass


class KnowledgeBaseServiceError(ActionError):
    """Exception for knowledge base operations."""

    pass
