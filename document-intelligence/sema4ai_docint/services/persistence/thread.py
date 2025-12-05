from .base import ParsedDocumentPersistence
from .file.chat_file_accessor import ChatFileAccessor


class ChatFilePersistenceService(ParsedDocumentPersistence):
    """
    Persistence service that writes cache entries to the Sema4.ai chat file APIs.
    If no chat_file_accessor is provided, this class will use the sema4ai.actions.chat
    API to interact with chat files.
    """

    def __init__(self, chat_file_accessor: ChatFileAccessor | None = None):
        from .file.actions_chat import ActionsChatFileAccessor

        self._chat_file_accessor = chat_file_accessor or ActionsChatFileAccessor()

    async def load(self, key: str) -> bytes | None:
        cache_key = self._cache_key_for(key)
        return await self._chat_file_accessor.read_text(cache_key)

    async def save(self, key: str, data: bytes) -> None:
        cache_key = self._cache_key_for(key)
        await self._chat_file_accessor.write_text(cache_key, data)
