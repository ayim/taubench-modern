from typing import Protocol


class ChatFileAccessor(Protocol):
    """Minimal interface for persisting files in the Sema4.ai conversation APIs."""

    async def write_text(self, name: str, content: bytes) -> None:
        """Write ``content`` to ``name`` overwriting any existing data."""

    async def read_text(self, name: str) -> bytes | None:
        """Read and return bytes from ``name``. If the file does not exist,
        return None."""

    async def list(self) -> list[str]:
        """Return file names."""
