from abc import abstractmethod
from typing import Protocol


class ParsedDocumentPersistence(Protocol):
    """Persistence interface for cached parse results."""

    def _cache_key_for(self, file_name: str) -> str:
        """Return the cache key for a file name."""
        return f"{file_name}.parse.json"

    @abstractmethod
    async def load(self, key: str) -> bytes | None:
        """Return the serialized parse result for ``key`` if it exists."""

    @abstractmethod
    async def save(self, key: str, data: bytes) -> None:
        """Persist a serialized parse result for ``key``."""
