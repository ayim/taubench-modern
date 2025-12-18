from abc import abstractmethod
from enum import Enum
from typing import Protocol


class DocumentOperationType(str, Enum):
    """Type of document intelligence operation for cache key generation."""

    PARSE = "parse"
    SCHEMA = "schema"
    EXTRACT = "extracted"  # Uses "extracted" for compatibility with existing caches


class DocumentPersistence(Protocol):
    """Persistence interface for document intelligence caching operations.

    This protocol provides a unified interface for caching all document operations
    (parse, schema generation, extraction) using a single service instance.
    """

    def cache_key_for(self, file_name: str, operation: DocumentOperationType) -> str:
        """Generate cache key for a specific operation type.

        Args:
            file_name: The file name to generate a cache key for
            operation: The type of operation (parse, schema, extract)

        Returns:
            Cache key in the format: {file_name}.{operation}.json
        """
        return f"{file_name}.{operation.value}.json"

    @abstractmethod
    async def load(self, cache_key: str) -> bytes | None:
        """Load cached data for the given cache key.

        Args:
            cache_key: The full cache key including suffix (e.g., "doc.pdf.parse.json")

        Returns:
            The cached data as bytes, or None if not found
        """

    @abstractmethod
    async def save(self, cache_key: str, data: bytes) -> None:
        """Save data to the given cache key.

        Args:
            cache_key: The full cache key including suffix (e.g., "doc.pdf.parse.json")
            data: The data to save as bytes
        """


# Backward compatibility aliases
ParsedDocumentPersistence = DocumentPersistence
