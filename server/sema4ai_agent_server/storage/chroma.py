from __future__ import annotations

from langchain_chroma import Chroma

from sema4ai_agent_server.storage.embed import BaseVectorStoreWrapper


class ChromaWrapper(Chroma, BaseVectorStoreWrapper):
    def delete_by_metadata(self, metadata_key: str, metadata_value: str) -> None:
        ids = self.get(where={metadata_key: metadata_value})["ids"]
        if ids:
            self.delete(ids)
