"""API to deal with file uploads via a runnable.

This module supports both PostgreSQL (PGVector) and SQLite (ChromaDB) as backend stores.
The choice is determined by the S4_AGENT_SERVER_DB_TYPE environment variable.
"""

from __future__ import annotations

import mimetypes
import os
from typing import Any, BinaryIO, List, Optional

from app.constants import VECTOR_DATABASE_PATH
from app.ingest import ingest_blob
from app.parsing import MIMETYPE_BASED_PARSER
from fastapi import UploadFile
from langchain_core.document_loaders.blob_loaders.schema import Blob
from langchain_core.runnables import (
    ConfigurableField,
    RunnableConfig,
    RunnableSerializable,
)
from langchain_core.vectorstores import VectorStore
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter


def get_vector_store() -> VectorStore:
    db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite").lower()

    if db_type == "postgres":
        from langchain_community.vectorstores.pgvector import PGVector

        PG_CONNECTION_STRING = PGVector.connection_string_from_db_params(
            driver="psycopg2",
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            database=os.environ.get("POSTGRES_DB", "sema4ai"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )

        return PGVector(
            connection_string=PG_CONNECTION_STRING,
            embedding_function=get_embeddings(),
            use_jsonb=True,
        )
    elif db_type == "sqlite":
        from langchain_chroma import Chroma

        return Chroma(
            persist_directory=VECTOR_DATABASE_PATH,
            embedding_function=get_embeddings(),
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_embeddings():
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIEmbeddings()
    elif os.environ.get("AZURE_OPENAI_API_KEY"):
        return AzureOpenAIEmbeddings(
            azure_endpoint=os.environ.get("AZURE_OPENAI_API_BASE"),
            azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME"),
            openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
        )
    else:
        raise ValueError(
            "Either OPENAI_API_KEY or AZURE_OPENAI_API_KEY needs to be set for embeddings to work."
        )


def _guess_mimetype(file_name: str, file_bytes: bytes) -> str:
    """Guess the mime-type of a file based on its name or bytes."""
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type:
        return mime_type

    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    elif file_bytes.startswith(
        (b"\x50\x4B\x03\x04", b"\x50\x4B\x05\x06", b"\x50\x4B\x07\x08")
    ):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    elif file_bytes.startswith(b"\x09\x00\xff\x00\x06\x00"):
        return "application/vnd.ms-excel"

    try:
        decoded = file_bytes[:1024].decode("utf-8", errors="ignore")
        if all(char in decoded for char in (",", "\n")) or all(
            char in decoded for char in ("\t", "\n")
        ):
            return "text/csv"
        elif decoded.isprintable() or decoded == "":
            return "text/plain"
    except UnicodeDecodeError:
        pass

    return "application/octet-stream"


def convert_ingestion_input_to_blob(file: UploadFile) -> Blob:
    """Convert ingestion input to blob."""
    file_data = file.file.read()
    file_name = file.filename

    if not isinstance(file_name, str):
        raise TypeError(f"Expected string for file name, got {type(file_name)}")

    mimetype = _guess_mimetype(file_name, file_data)
    return Blob.from_data(
        data=file_data,
        path=file_name,
        mime_type=mimetype,
    )


class IngestRunnable(RunnableSerializable[BinaryIO, List[str]]):
    """Runnable for ingesting files into a vectorstore."""

    text_splitter: TextSplitter
    vectorstore: VectorStore
    assistant_id: Optional[str]
    thread_id: Optional[str]

    class Config:
        arbitrary_types_allowed = True

    @property
    def namespace(self) -> str:
        if (self.assistant_id is None and self.thread_id is None) or (
            self.assistant_id is not None and self.thread_id is not None
        ):
            raise ValueError(
                "Exactly one of assistant_id or thread_id must be provided"
            )
        return self.assistant_id if self.assistant_id is not None else self.thread_id

    def invoke(self, blob: Blob, config: Optional[RunnableConfig] = None) -> List[str]:
        return self.batch([blob], config)

    def batch(
        self,
        inputs: List[Blob],
        config: RunnableConfig | List[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any | None,
    ) -> List:
        """Ingest a batch of files into the vectorstore."""
        ids = []
        for blob in inputs:
            ids.extend(
                ingest_blob(
                    blob,
                    MIMETYPE_BASED_PARSER,
                    self.text_splitter,
                    self.vectorstore,
                    self.namespace,
                )
            )
        return ids


# Initialize the vector store
vstore = get_vector_store()

ingest_runnable = IngestRunnable(
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200),
    vectorstore=vstore,
).configurable_fields(
    assistant_id=ConfigurableField(
        id="assistant_id",
        annotation=str,
        name="Assistant ID",
    ),
    thread_id=ConfigurableField(
        id="thread_id",
        annotation=str,
        name="Thread ID",
    ),
)
