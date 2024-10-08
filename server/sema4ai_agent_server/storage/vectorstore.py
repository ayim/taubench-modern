from abc import ABC, abstractmethod
from uuid import UUID

from langchain_chroma import Chroma
from langchain_community.vectorstores import PGEmbedding
from langchain_core.vectorstores import VectorStore
from langchain_postgres import PGVector
from sqlalchemy.orm import Session


class VectorStoreBase(VectorStore, ABC):
    @abstractmethod
    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        """Delete a vector by it's metadata key file_id."""
        pass


class PostgresVector(PGVector, VectorStoreBase):
    def __init__(self, embeddings, connection_string, use_jsonb, async_mode):
        self.connection_string = connection_string
        super().__init__(
            embeddings=embeddings,
            connection=connection_string,
            use_jsonb=use_jsonb,
            async_mode=async_mode,
        )

    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        ids = await self._get_pg_embeddings("file_id", file_id)
        if ids:
            await self.adelete(ids)

    async def _fetch_document_ids(
        self, session: Session, metadata_key: str, metadata_value: str
    ) -> list[str]:
        await self.__apost_init__()
        document_ids = (
            session.query(self.EmbeddingStore.id)
            .filter(
                self.EmbeddingStore.cmetadata[metadata_key].astext == metadata_value
            )
            .all()
        )
        return [id[0] for id in document_ids]

    async def _get_pg_embeddings(
        self, metadata_key: str, metadata_value: str
    ) -> list[str]:
        pg_embedding = PGEmbedding(self.connection_string, self.embedding_function)
        conn = pg_embedding.connect()
        with Session(conn) as session:
            ids = await self._fetch_document_ids(session, metadata_key, metadata_value)
        conn.close()
        return ids


class ChromaVector(Chroma, VectorStoreBase):
    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        ids = self.get(where={"file_id": file_id})["ids"]
        if ids:
            self.delete(ids)
