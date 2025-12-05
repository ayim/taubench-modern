"""Persistence implementation that writes cache entries to a directory."""

from pathlib import Path

from .base import ParsedDocumentPersistence


class DirectoryPersistenceService(ParsedDocumentPersistence):
    """Persistence service writing serialized parse results to disk."""

    def __init__(self, directory: Path | str) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, name: str) -> Path:
        cache_key = self._cache_key_for(name)
        return self._directory / cache_key

    async def load(self, name: str) -> bytes | None:
        path = self._path_for(name)
        if not path.exists():
            return None
        return path.read_bytes()

    async def save(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.write_bytes(data)
