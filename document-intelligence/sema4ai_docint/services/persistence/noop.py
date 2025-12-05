"""No-op persistence implementation used when caching is disabled."""

from .base import ParsedDocumentPersistence


class NoOpPersistenceService(ParsedDocumentPersistence):
    """Persistence service that never stores or returns cached data."""

    async def load(self, key: str) -> bytes | None:
        return None

    async def save(self, key: str, data: bytes) -> None:
        pass
