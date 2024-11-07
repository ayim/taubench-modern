import os
from typing import Union
from uuid import uuid4

import structlog
from agent_server_types import (
    Agent,
    EmbeddingStatus,
    Thread,
    UploadedFile,
)
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import (
    MISSING_FILE_HASH,
    BaseFileManager,
    RemoteFileUploadData,
    get_hash,
)
from sema4ai_agent_server.schema import UploadFileRequest
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

    async def _revert_uploads(self, uploads: list[tuple[str, str]]) -> None:
        """uploads is a list of tuples of the form (file_id, file_path)"""
        for file_id, file_path in uploads:
            await self._delete_stored_file(file_path)
            await get_storage().delete_file(file_id)

    async def _upload(
        self,
        file_id: str,
        file_path: str,
        file: UploadFile,
        owner: Union[Agent, Thread],
        embedded: bool,
    ) -> UploadedFile:
        blob = convert_to_blob(file)
        file_hash = await self._store(blob, file_path)
        return await get_storage().put_file_owner(
            file_id,
            file_path,
            file.filename,
            file_hash,
            embedded,
            EmbeddingStatus.PENDING if embedded else None,
            owner,
            file_path_expiration=None,
        )

    async def upload(
        self, files: list[UploadFileRequest], owner: Union[Agent, Thread]
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        self._validate_files_pre_upload(files)
        owner_id = owner.id if isinstance(owner, Agent) else owner.thread_id
        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            file_path = self._build_file_path(owner_id, file_id, f.file.filename)
            embedded = (
                f.embedded if f.embedded is not None else self._is_embeddable(f.file)
            )
            try:
                uploaded_file = await self._upload(
                    file_id, file_path, f.file, owner, embedded
                )
            except Exception as e:
                logger.exception(
                    f"Failed to upload {f.file.filename}. Reverting all uploads."
                )
                await self._revert_uploads(
                    [(file_id, file_path)]
                    + [(file.file_id, file.file_path) for file in uploaded_files]
                )
                raise e
            uploaded_files.append(uploaded_file)
        return uploaded_files

    async def delete(self, file_id: str) -> None:
        file = await get_storage().get_file_by_id(file_id)
        await self._delete_stored_file(file.file_path)
        await self._delete_embeddings(file_id)
        await get_storage().delete_file(file_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        """Paths are not presigned in local storage"""
        return files

    async def read_file_contents(self, file_id: str) -> bytes:
        file = await get_storage().get_file_by_id(file_id)
        if not file:
            raise Exception(f"File not found: {file_id}")
        try:
            with open(file.file_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.exception(f"File not found: {file.file_path}")
            raise

    def _build_file_path(self, owner_id: str, file_id: str, file_ref: str) -> str:
        return os.path.abspath(os.path.join(UPLOAD_DIR, owner_id, file_id, file_ref))

    async def request_remote_file_upload(
        self, thread: Thread, file_name: str
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        file_ref = await self.generate_unique_file_ref(thread, file_name)
        url = self._build_file_path(thread.thread_id, file_id, file_ref)
        return RemoteFileUploadData(
            url=url,
            form_data={},
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self, thread: Thread, file_ref: str, file_id: str
    ) -> UploadedFile:
        file = await get_storage().put_file_owner(
            file_id=file_id,
            file_path=self._build_file_path(thread.thread_id, file_id, file_ref),
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            embedded=False,
            embedding_status=None,
            owner=thread,
            file_path_expiration=None,
        )
        return file
