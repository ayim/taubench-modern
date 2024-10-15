"""API to deal with file uploads via a runnable.

This module supports both PostgreSQL (PGVector) and SQLite (ChromaDB) as backend stores.
"""

from __future__ import annotations

import mimetypes
import os
from asyncio import get_event_loop
from typing import BinaryIO, List, Optional, Union

import boto3
from fastapi import UploadFile
from langchain_aws import BedrockEmbeddings
from langchain_community.document_loaders.base import BaseBlobParser
from langchain_core.document_loaders.blob_loaders import Blob
from langchain_core.documents import Document
from langchain_core.runnables import (
    ConfigurableField,
    RunnableConfig,
    RunnableSerializable,
)
from langchain_core.vectorstores import VectorStore
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter
from pydantic import ConfigDict, Field

from sema4ai_agent_server.constants import VECTOR_DATABASE_PATH
from sema4ai_agent_server.parsing import MIMETYPE_BASED_PARSER
from sema4ai_agent_server.schema import (
    MODEL,
    NOT_CONFIGURED,
    AmazonBedrock,
    AzureGPT,
    OpenAIGPT,
    dummy_model,
)
from sema4ai_agent_server.storage.vectorstore import (
    ChromaVector,
    PostgresVector,
    VectorStoreBase,
)


def _update_document_metadata(document: Document, owner_id: str, file_id: str) -> None:
    document.metadata["owner_id"] = owner_id
    document.metadata["file_id"] = file_id


def _sanitize_document_metadata(document: Document) -> Document:
    """Chroma doesn't accept None values in metadata, so we replace them."""
    for k, v in document.metadata.items():
        if v is None:
            document.metadata[k] = ""


def _sanitize_document_content(document: Document) -> Document:
    """Sanitize the document."""
    # Without this, PDF embedding fails with
    # "A string literal cannot contain NUL (0x00) characters".
    document.page_content = document.page_content.replace("\x00", "x")


async def aembed_blob(
    blob: Blob,
    parser: BaseBlobParser,
    text_splitter: TextSplitter,
    vectorstore: VectorStore,
    owner_id: str,
    file_id: str,
    *,
    batch_size: int = 100,
) -> List[str]:
    """Embed a document into the vectorstore."""
    docs_to_index = []
    ids = []
    for document in parser.lazy_parse(blob):
        docs = text_splitter.split_documents([document])
        for doc in docs:
            _sanitize_document_content(doc)
            _sanitize_document_metadata(doc)
            _update_document_metadata(doc, owner_id, file_id)
        docs_to_index.extend(docs)

        if len(docs_to_index) >= batch_size:
            ids.extend(await vectorstore.aadd_documents(docs_to_index))
            docs_to_index = []

    if docs_to_index:
        ids.extend(await vectorstore.aadd_documents(docs_to_index))

    return ids


def guess_mimetype(file_name: str, file_bytes: bytes) -> str:
    """Guess the mime-type of a file based on its name or bytes."""
    # Guess based on the file extension
    mime_type, _ = mimetypes.guess_type(file_name)

    # Return detected mime type from mimetypes guess, unless it's None
    if mime_type:
        return mime_type

    # Signature-based detection for common types
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    elif file_bytes.startswith(
        (b"\x50\x4b\x03\x04", b"\x50\x4b\x05\x06", b"\x50\x4b\x07\x08")
    ):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    elif file_bytes.startswith(b"\x09\x00\xff\x00\x06\x00"):
        return "application/vnd.ms-excel"

    # Check for CSV-like plain text content (commas, tabs, newlines)
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


def convert_to_blob(file: UploadFile) -> Blob:
    """Convert file to blob."""
    file_data = file.file.read()
    file_name = file.filename

    # Check if file_name is a valid string
    if not isinstance(file_name, str):
        raise TypeError(f"Expected string for file name, got {type(file_name)}")

    mimetype = guess_mimetype(file_name, file_data)
    return Blob.from_data(
        data=file_data,
        path=file_name,
        mime_type=mimetype,
    )


def get_embedding_function(
    model: MODEL,
) -> Union[OpenAIEmbeddings, AzureOpenAIEmbeddings]:
    if isinstance(model, OpenAIGPT):
        return OpenAIEmbeddings(
            openai_api_key=model.config.openai_api_key.get_secret_value(),
        )
    elif isinstance(model, AzureGPT):
        return AzureOpenAIEmbeddings(
            azure_endpoint=model.config.embeddings_azure_endpoint,
            azure_deployment=model.config.embeddings_deployment_name,
            openai_api_version=model.config.embeddings_openai_api_version,
            openai_api_key=model.config.embeddings_openai_api_key.get_secret_value(),
        )
    elif isinstance(model, AmazonBedrock):
        client = boto3.client(
            model.config.service_name,
            region_name=model.config.region_name,
            aws_access_key_id=model.config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=model.config.aws_secret_access_key.get_secret_value(),
        )
        return BedrockEmbeddings(client=client, model_id="amazon.titan-embed-text-v2:0")
    raise ValueError(f"Unsupported model type {model} for embeddings.")


def _get_pg_vector(model: Optional[MODEL]) -> PostgresVector:
    connection_string = PostgresVector.connection_string_from_db_params(
        driver="psycopg",
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    return PostgresVector(
        embeddings=get_embedding_function(model) if model else None,
        connection_string=connection_string,
        use_jsonb=True,
        async_mode=True,
    )


def _get_chroma_vector(model: Optional[MODEL]) -> ChromaVector:
    return ChromaVector(
        # OpenAI's vector size is 1536, while AWS's titan model generates vectors with size 1024.
        # Chroma can't use the same collection for both, because it will throw an error when
        # adding documents with mismatched vector sizes. So, we use model provider as the
        # collection name to avoid this issue.
        collection_name=model.provider.value or "default",
        persist_directory=VECTOR_DATABASE_PATH,
        embedding_function=get_embedding_function(model) if model else None,
    )


def get_vector_store(model: Optional[MODEL] = None) -> VectorStoreBase:
    db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    if db_type == "postgres":
        return _get_pg_vector(model)
    elif db_type == "sqlite":
        return _get_chroma_vector(model)
    raise ValueError("Invalid storage type")


class EmbedRunnable(RunnableSerializable[BinaryIO, List[str]]):
    """Runnable for embedding files into a vectorstore."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text_splitter: TextSplitter = Field(
        ..., description="Text splitter to use for splitting the text into chunks."
    )
    model: MODEL | None = Field(None, description="Model to use for embedding.")
    file_id: str | None = Field(None, description="ID of the file to embed.")
    owner_id: str | None = Field(
        None, description="ID of the file owner (agent or thread)."
    )

    # PGVector doesn't support sync mode, so we use async mode in all cases. Chroma
    # won't be affected by this because sync mode is invoked directly from the async
    # base methods from VectorStore.
    def invoke(self, blob: Blob, config: Optional[RunnableConfig] = None) -> List[str]:
        return get_event_loop().run_until_complete(self.ainvoke(blob, config))

    async def ainvoke(
        self, blob: Blob, config: Optional[RunnableConfig] = None
    ) -> List[str]:
        out = await aembed_blob(
            blob,
            MIMETYPE_BASED_PARSER,
            self.text_splitter,
            get_vector_store(self.model),
            self.owner_id,
            self.file_id,
        )
        return out


embed_runnable = EmbedRunnable(
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200),
    model=dummy_model,
    file_id=NOT_CONFIGURED,
    owner_id=NOT_CONFIGURED,
).configurable_fields(
    owner_id=ConfigurableField(
        id="owner_id",
        annotation=str,
        name="Owner ID (agent's id or thread's id)",
    ),
    file_id=ConfigurableField(
        id="file_id",
        annotation=str,
        name="File ID",
    ),
    model=ConfigurableField(
        id="model",
        annotation=MODEL,
        name="model",
    ),
)
