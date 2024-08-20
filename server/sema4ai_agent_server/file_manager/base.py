import hashlib
import os
from enum import Enum
from typing import Union

import structlog
from fastapi import UploadFile

from sema4ai_agent_server.schema import Assistant, Thread, UploadedFile
from sema4ai_agent_server.storage.embed import Blob, embed_runnable, vstore
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
        self,
        file: UploadFile,
        owner: Union[Assistant, Thread],
    ) -> UploadedFile:
        raise NotImplementedError()

    async def delete(self, file_id: str) -> None:
        raise NotImplementedError()

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        raise NotImplementedError()

    def _delete_embeddings(self, file_id: str) -> None:
        vstore.delete_by_metadata("file_id", file_id)

    def _create_embeddings(
        self, blob: Blob, owner: Union[Assistant, Thread], file_id: str
    ) -> None:
        owner_id: str = owner.get("thread_id", owner.get("assistant_id", "NO OWNER"))
        config = {"configurable": {"owner_id": owner_id, "file_id": file_id}}
        try:
            embed_runnable.invoke(blob, config)
        except ValueError:
            # Raised by LangChain if mimetype is not supported
            logger.exception(f"Failed to embed file {file_id}")
            raise FileEmbeddingFailed()

    def _is_embeddable(self, file: UploadFile) -> bool:
        file_extension = os.path.splitext(file.filename)[1].lower()
        return file_extension not in NON_EMBEDDABLE_EXTENSIONS

    async def _validate_file_uniqueness(
        self, file: UploadFile, owner: Union[Assistant, Thread]
    ) -> None:
        if await get_storage().get_file(owner, file.filename):
            raise FileAlreadyExists()


def get_hash(file_data: bytes) -> str:
    hash = hashlib.sha256()
    hash.update(file_data)
    return hash.hexdigest()
