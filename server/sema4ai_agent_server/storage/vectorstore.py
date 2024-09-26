from abc import ABC, abstractmethod
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStore
from langchain_postgres import PGVector


class VectorStoreBase(VectorStore, ABC):
    @abstractmethod
    def adelete_by_file_id(self, file_id: str | UUID) -> None:
        """Delete a vector by it's metadata key file_id."""
        pass


class PostgresVector(PGVector, VectorStoreBase):
    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        # TODO: implement... I think this can be done by getting a
        # session from the VectorStore.session_maker property and
        # then using the VectorStore.embeddings property to help
        # build a query? That or we need to perform so lower level stuff
        # by looking at how they implemented some of the other methods.
        raise NotImplementedError("Not implemented yet")


class ChromaVector(Chroma, VectorStoreBase):
    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        # TODO: implement
        raise NotImplementedError("Not implemented yet")
