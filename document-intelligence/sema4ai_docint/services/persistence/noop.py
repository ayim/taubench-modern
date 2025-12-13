"""No-op persistence implementation used when caching is disabled."""

from .base import DocumentOperationType, DocumentPersistence


class NoOpPersistenceService(DocumentPersistence):
    """Persistence service that never stores or returns cached data.

    This unified service handles all document operations (parse, schema, extract)
    but performs no actual caching.
    """

    def cache_key_for(self, file_name: str, operation: DocumentOperationType) -> str:
        """Generate cache key (not used since no caching occurs).

        Args:
            file_name: The file name to generate a cache key for
            operation: The type of operation (parse, schema, extract)

        Returns:
            Cache key in the format: {file_name}.{operation}.json
        """
        return f"{file_name}.{operation.value}.json"

    async def load(self, cache_key: str) -> bytes | None:
        """Always returns None (no caching)."""
        return None

    async def save(self, cache_key: str, data: bytes) -> None:
        """Does nothing (no caching)."""
