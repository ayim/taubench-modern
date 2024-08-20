import os
from typing import Union
from uuid import uuid4

import structlog
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import BaseFileManager, get_hash
from sema4ai_agent_server.schema import Assistant, Thread, UploadedFile
from sema4ai_agent_server.storage.embed import Blob, convert_to_blob
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)


SEMA4AIDESKTOP_HOME = os.getenv("S4_AGENT_SERVER_HOME", ".")
UPLOAD_DIR = os.path.join(SEMA4AIDESKTOP_HOME, "uploads")


class LocalFileManager(BaseFileManager):
    async def _store(self, blob: Blob, file_path: str) -> str:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(blob.data)
        return get_hash(blob.data)

    async def _delete_stored_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)

    async def _revert_upload(self, file_id: str, file_path: str) -> None:
        await self._delete_stored_file(file_path)
        self._delete_embeddings(file_id)
        await get_storage().delete_file(file_id)

    async def _upload(
        self,
        file_id: str,
        file_path: str,
        file: UploadFile,
        owner: Union[Assistant, Thread],
    ) -> UploadedFile:
        await self._validate_file_uniqueness(file, owner)

        blob = convert_to_blob(file)

        file_hash = await self._store(blob, file_path)

        embeddable = self._is_embeddable(file)
        if embeddable:
            self._create_embeddings(blob, owner, file_id)

        return await get_storage().put_file_owner(
            file_id,
            file_path,
            file.filename,
            file_hash,
            embeddable,
            owner,
            file_path_expiration=None,
        )

    async def upload(
        self,
        file: UploadFile,
        owner: Union[Assistant, Thread],
    ) -> UploadedFile:
        file_id = str(uuid4())
        file_path = os.path.abspath(
            os.path.join(
                UPLOAD_DIR,
                owner.get("thread_id", owner.get("assistant_id", "NO_OWNER")),
                file_id,
                file.filename,
            )
        )
        try:
            return await self._upload(file_id, file_path, file, owner)
        except Exception as e:
            logger.exception(f"Failed to upload file {file.filename}")
            await self._revert_upload(file_id, file_path)
            raise e

    async def delete(self, file_id: str) -> None:
        file = await get_storage().get_file_by_id(file_id)
        await self._delete_stored_file(file["file_path"])
        self._delete_embeddings(file_id)
        await get_storage().delete_file(file_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        """Paths are not presigned in local storage"""
        return files
