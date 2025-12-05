import asyncio

from .chat_file_accessor import ChatFileAccessor


class ActionsChatFileAccessor(ChatFileAccessor):
    """File accessor backed by the Sema4.ai actions.chat API. Should only be
    used for building custom Sema4.ai Action Packages."""

    async def write_text(self, name: str, content: bytes) -> None:
        from sema4ai.actions.chat import attach_file_content

        await asyncio.to_thread(attach_file_content, name, content)

    async def read_text(self, name: str) -> bytes | None:
        from sema4ai.actions.chat import get_file_content, list_files

        all_files = list_files()
        if name not in all_files:
            return None

        return await asyncio.to_thread(get_file_content, name)

    async def list(self) -> list[str]:
        from sema4ai.actions.chat import list_files

        return list_files()
