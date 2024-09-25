import hashlib
import os
from enum import Enum
from typing import Union

import structlog
from fastapi import UploadFile

from sema4ai_agent_server.schema import (
    MODEL,
    Agent,
    EmbeddingStatus,
    Thread,
    UploadedFile,
    UploadFileRequest,
)
from sema4ai_agent_server.storage.embed import (
    Blob,
    embed_runnable,
    get_vector_store,
    guess_mimetype,
)
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

NON_EMBEDDABLE_EXTENSIONS = {".csv", ".xls", ".xlsx", ".json", ".xml"}


class FileUploadFailReason(str, Enum):
    ALREADY_EXISTS = "file_already_exists"
    EMBEDDING_FAILED = "file_embedding_failed"
    UNKNOWN = "unknown"


class UploadFailed(Exception):
    reason: FileUploadFailReason = FileUploadFailReason.UNKNOWN


class FileAlreadyExists(UploadFailed):
    reason = FileUploadFailReason.ALREADY_EXISTS


class FileEmbeddingFailed(UploadFailed):
    reason = FileUploadFailReason.EMBEDDING_FAILED


class BaseFileManager:
    async def upload(
        self, files: list[UploadFileRequest], owner: Union[Agent, Thread]
    ) -> list[UploadedFile]:
        raise NotImplementedError()

    async def delete(self, file_id: str) -> None:
        raise NotImplementedError()

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        raise NotImplementedError()

    async def read_file_contents(self, file_id: str) -> bytes:
        raise NotImplementedError()

    def _delete_embeddings(self, file_id: str) -> None:
        get_vector_store().delete_by_metadata("file_id", file_id)

    async def create_embeddings(self, file: UploadedFile, model: MODEL) -> None:
        owner_id = file.agent_id if file.agent_id else file.thread_id
        config = {
            "configurable": {
                "owner_id": owner_id,
                "file_id": file.file_id,
                "model": model,
            }
        }
        data = await self.read_file_contents(file.file_id)
        mimetype = guess_mimetype(file.file_ref, data)
        blob = Blob.from_data(data=data, path=file.file_ref, mime_type=mimetype)

        await get_storage().update_file_embedding_status(
            file.file_id, embedding_status=EmbeddingStatus.IN_PROGRESS
        )
        try:
            embed_runnable.invoke(blob, config)
        except Exception as e:
            logger.exception(f"Failed to embed file {file.file_ref}", exception=e)
            await get_storage().update_file_embedding_status(
                file.file_id, embedding_status=EmbeddingStatus.FAILURE
            )
            raise FileEmbeddingFailed()
        else:
            await get_storage().update_file_embedding_status(
                file.file_id, embedding_status=EmbeddingStatus.SUCCESS
            )

    async def create_missing_embeddings(
        self, model: MODEL, owner: Union[Agent, Thread]
    ) -> None:
        model_is_configured, _ = model.config.is_configured()
        if not model_is_configured:
            logger.info("Skipping creating file embeddings. Model is not configured.")
            return

        files = []
        if isinstance(owner, Agent):
            files = await get_storage().get_agent_files(owner.id)
        elif isinstance(owner, Thread):
            files = await get_storage().get_thread_files(owner.thread_id)

        for file in files:
            if file.embedded and file.embedding_status in (
                EmbeddingStatus.PENDING,
                EmbeddingStatus.FAILURE,
            ):
                logger.info(f"Creating embeddings for {file.file_ref}")
                try:
                    await self.create_embeddings(file, model)
                except FileEmbeddingFailed:
                    pass
            else:
                logger.info(
                    f"Skipping creating embeddings for {file.file_ref}. "
                    f"Should be embedded: {file.embedded}. "
                    f"Status: {file.embedding_status}."
                )

    def _is_embeddable(self, file: UploadFile) -> bool:
        file_extension = os.path.splitext(file.filename)[1].lower()
        return file_extension not in NON_EMBEDDABLE_EXTENSIONS

    async def _validate_file_uniqueness(
        self, file: UploadFile, owner: Union[Agent, Thread]
    ) -> None:
        if await get_storage().get_file(owner, file.filename):
            raise FileAlreadyExists()


def get_hash(file_data: bytes) -> str:
    hash = hashlib.sha256()
    hash.update(file_data)
    return hash.hexdigest()
