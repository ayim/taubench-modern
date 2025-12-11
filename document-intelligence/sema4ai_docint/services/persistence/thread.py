from .base import DocumentOperationType, DocumentPersistence
from .file.chat_file_accessor import ChatFileAccessor


class ChatFilePersistenceService(DocumentPersistence):
    """Persistence service that writes cache entries to the Sema4.ai chat file APIs.

    This unified service handles caching for all document operations (parse, schema, extract)
    using a single implementation with operation-specific cache keys.

    If no chat_file_accessor is provided, this class will use the sema4ai.actions.chat
    API to interact with chat files.
    """

    def __init__(self, chat_file_accessor: ChatFileAccessor | None = None):
        from .file.actions_chat import ActionsChatFileAccessor

        self._chat_file_accessor = chat_file_accessor or ActionsChatFileAccessor()

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
        return await self._chat_file_accessor.read_text(cache_key)

    async def save(self, cache_key: str, data: bytes) -> None:
        """Save data to the given cache key.

        Args:
            cache_key: The full cache key (e.g., "doc.pdf.parse.json" or "doc.pdf.schema.json")
            data: The data to save as bytes
        """
        await self._chat_file_accessor.write_text(cache_key, data)
