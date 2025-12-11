"""Persistence implementation that writes cache entries to a directory."""

from pathlib import Path

from .base import DocumentOperationType, DocumentPersistence


class DirectoryPersistenceService(DocumentPersistence):
    """Persistence service writing serialized results to disk.

    This unified service handles caching for all document operations (parse, schema, extract)
    using a single implementation with operation-specific cache keys.
    """

    def __init__(self, directory: Path | str) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def cache_key_for(self, file_name: str, operation: DocumentOperationType) -> str:
        """Generate cache key for a specific operation type.

        Args:
            file_name: The file name to generate a cache key for
            operation: The type of operation (parse, schema, extract)

        Returns:
            Cache key in the format: {file_name}.{operation}.json
        """
        return f"{file_name}.{operation.value}.json"

    async def load(self, cache_key: str) -> bytes | None:
        """Load cached data from the given cache key.

        Args:
            cache_key: The full cache key (e.g., "doc.pdf.parse.json" or "doc.pdf.schema.json")

        Returns:
            The cached data as bytes, or None if not found
        """
        path = self._directory / cache_key
        if not path.exists():
            return None
        return path.read_bytes()

    async def save(self, cache_key: str, data: bytes) -> None:
        """Save data to the given cache key.

        Args:
            cache_key: The full cache key (e.g., "doc.pdf.parse.json" or "doc.pdf.schema.json")
            data: The data to save as bytes
        """
        path = self._directory / cache_key
        path.write_bytes(data)
