from pathlib import Path

from pydantic import BaseModel

from sema4ai_docint.agent_server_client.transport import TransportBase


class DocumentV2(BaseModel):
    file_name: str
    document_id: str
    local_file_path: Path | None = None

    def get_local_path(self, agent_server_transport: TransportBase) -> Path:
        """Returns a localized path to this file. If the file is not localized, it will be
        localized and cached."""
        if self.local_file_path is not None:
            return self.local_file_path

        self.local_file_path = agent_server_transport.get_file(self.file_name)
        return self.local_file_path
