from pathlib import Path

from pydantic import BaseModel

from sema4ai_docint.agent_server_client.transport import DirectTransport, TransportBase
from sema4ai_docint.agent_server_client.transport._utils import call_transport_method_async


class DocumentV2(BaseModel):
    file_name: str
    document_id: str
    local_file_path: Path | None = None

    async def get_local_path(self, agent_server_transport: TransportBase | DirectTransport) -> Path:
        """Returns a localized path to this file. If the file is not localized, it will be
        localized and cached."""
        if self.local_file_path is not None:
            return self.local_file_path

        local_path = await call_transport_method_async(
            agent_server_transport, "get_file", self.file_name
        )
        self.local_file_path = local_path
        return local_path
