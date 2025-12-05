"""
Service layer for document intelligence operations.

This module provides high-level business logic services that orchestrate
interactions between models, extraction, and other components.
"""

from .di_service import (
    DIService,
    build_di_service,
    build_extraction_service,
    build_extraction_service_async,
)
from .dto import KnowledgeBaseQueryResult
from .exceptions import (
    DataModelServiceError,
    DocumentServiceError,
    ExtractionServiceError,
    LayoutServiceError,
)

__all__ = [
    # Services
    "DIService",
    "DataModelServiceError",
    "DocumentServiceError",
    "ExtractionServiceError",
    "KnowledgeBaseQueryResult",
    "LayoutServiceError",
    "build_di_service",
    "build_extraction_service",
    "build_extraction_service_async",
]
