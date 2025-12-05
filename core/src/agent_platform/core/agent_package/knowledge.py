from collections.abc import Mapping
from dataclasses import dataclass
from typing import IO


@dataclass(frozen=True)
class KnowledgeStreams:
    """Context manager for knowledge file streams from an agent package."""

    _streams: Mapping[str, IO[bytes]]

    def __enter__(self) -> Mapping[str, IO[bytes]]:
        """Return the mapping of filename to file-like objects."""
        return self._streams

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close all file streams when exiting the context."""
        for stream in self._streams.values():
            stream.close()
