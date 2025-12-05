from unittest.mock import AsyncMock, MagicMock

import pytest

from sema4ai_docint.services.persistence import (
    ActionsChatFileAccessor,
    ChatFileAccessor,
    ChatFilePersistenceService,
)


class TestChatFilePersistenceService:
    """Test suite for ChatFilePersistenceService."""

    @pytest.mark.asyncio
    async def test_init_chat_file_persistence(self):
        service = ChatFilePersistenceService()
        assert isinstance(service._chat_file_accessor, ActionsChatFileAccessor), (
            "Expected the accessor to be initialized with the ActionsChatFileAccessor"
        )

    @pytest.mark.asyncio
    async def test_init_chat_file_persistence_with_custom_accessor(self):
        accessor = MagicMock(spec=ChatFileAccessor)
        service = ChatFilePersistenceService(accessor)
        assert service._chat_file_accessor is accessor, (
            "Expected the accessor to be initialized with the custom accessor"
        )

    @pytest.mark.asyncio
    async def test_load_and_save(self):
        mock_accessor = AsyncMock(spec=ChatFileAccessor)
        service = ChatFilePersistenceService(chat_file_accessor=mock_accessor)

        file_name = "foo.txt"
        cache_key = "foo.txt.parse.json"

        # Cache miss
        mock_accessor.read_text.return_value = None
        assert await service.load(file_name) is None, "Expected the content to be None"
        mock_accessor.read_text.assert_called_once_with(cache_key)

        # Cache load
        expected_content = b"Hello, world!"
        await service.save(file_name, expected_content)
        mock_accessor.write_text.assert_called_once_with(cache_key, expected_content)

        # Cache hit
        mock_accessor.reset_mock()
        mock_accessor.read_text.return_value = expected_content
        assert await service.load(file_name) == expected_content, (
            "Expected the content to be the same"
        )
        mock_accessor.read_text.assert_called_once_with(cache_key)
