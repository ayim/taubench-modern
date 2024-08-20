from __future__ import annotations

import os
from typing import List

from langchain_community.vectorstores import PGEmbedding, PGVector
from langchain_community.vectorstores.pgembedding import EmbeddingStore
from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from sema4ai_agent_server.storage.embed import BaseVectorStoreWrapper


class PGVectorWrapper(PGVector, BaseVectorStoreWrapper):
    def _fetch_document_ids(
        self, session: Session, metadata_key: str, metadata_value: str
    ) -> List[str]:
        document_ids = (
            session.query(EmbeddingStore.custom_id)
            .filter(EmbeddingStore.cmetadata[metadata_key].astext == metadata_value)
            .all()
        )
        return [id[0] for id in document_ids]

    def _get_pg_embeddings(self, metadata_key: str, metadata_value: str) -> list[str]:
        pg_embedding = PGEmbedding(self.connection_string, self.embedding_function)
        conn = pg_embedding.connect()
        with Session(conn) as session:
            ids = self._fetch_document_ids(session, metadata_key, metadata_value)
        conn.close()
        return ids

    def delete_by_metadata(self, metadata_key: str, metadata_value: str) -> None:
        ids = self._get_pg_embeddings(metadata_key, metadata_value)
        if ids:
            self.delete(ids)


def get_pg_vector_wrapper(embedding_function: Embeddings) -> PGVectorWrapper:
    PG_CONNECTION_STRING = PGVector.connection_string_from_db_params(
        driver="psycopg2",
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    return PGVectorWrapper(
        connection_string=PG_CONNECTION_STRING,
        embedding_function=embedding_function,
        use_jsonb=True,
    )
