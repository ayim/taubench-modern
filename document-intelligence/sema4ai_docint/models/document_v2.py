from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel

from sema4ai_docint.agent_server_client.transport import DirectTransport, TransportBase


class DocumentV2(BaseModel):
    file_name: str
    document_id: str

    @asynccontextmanager
    async def get_local_path(
        self, agent_server_transport: TransportBase | DirectTransport
    ) -> AsyncIterator[Path]:
        """Returns a localized path to this file as an async context manager.

        For remote files that are downloaded to temp locations, the file is
        automatically cleaned up when the context exits.
        """
        from sema4ai_docint.agent_server_client.transport._utils import get_file_async

        async with get_file_async(agent_server_transport, self.file_name) as path:
            yield path
