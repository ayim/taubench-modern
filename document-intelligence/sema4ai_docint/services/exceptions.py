"""
Custom exceptions for document intelligence services.
"""

from sema4ai.actions import ActionError


class DocumentServiceError(ActionError):
    """Base exception for document service operations."""


class LayoutServiceError(ActionError):
    """Exception for document layout operations."""


class DataModelServiceError(ActionError):
    """Exception for data model operations."""


class ExtractionServiceError(ActionError):
    """Exception for extraction operations."""


class KnowledgeBaseServiceError(ActionError):
    """Exception for knowledge base operations."""
