import json
import os
from datetime import datetime, timedelta, timezone
from typing import Union
from uuid import uuid4

import requests
import structlog
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import (
    BaseFileManager,
    RemoteFileUploadData,
    get_hash,
)
from sema4ai_agent_server.schema import (
    Agent,
    EmbeddingStatus,
    Thread,
    UploadedFile,
    UploadFileRequest,
)
from sema4ai_agent_server.storage.embed import Blob, convert_to_blob
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)


FILE_MANAGEMENT_API_URL = os.getenv("FILE_MANAGEMENT_API_URL")


class CloudFileManager(BaseFileManager):
    FILE_PATH_EXPIRES_IN = 43200  # 12 hours
    FILE_PATH_EXPIRATION_BUFFER = 300  # 5 minutes

    def _get_presigned_post(self, file_id: str) -> dict:
        response = requests.post(
            f"{FILE_MANAGEMENT_API_URL}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fileId": file_id, "expiresIn": 300}),
        )
        return response.json()

    def _get_presigned_url(self, file_id: str, file_name: str) -> str:
        response = requests.get(
            f"{FILE_MANAGEMENT_API_URL}",
            headers={"Content-Type": "application/json"},
            params={
                "fileId": file_id,
                "expiresIn": self.FILE_PATH_EXPIRES_IN,
                "fileName": file_name,
            },
        )
        return response.json()["url"]

    async def _store(self, blob: Blob, file_id: str) -> str:
        presigned_post = self._get_presigned_post(file_id)
        payload = presigned_post["form_data"]
        response = requests.post(
            presigned_post["url"], data=payload, files={"file": blob.data}
        )
        if response.status_code != 204:
            logger.error(
                f"Failed to upload file {blob.path}", status_code=response.status_code
            )
            raise Exception("Failed to upload file")

        return get_hash(blob.data)

    async def _delete_stored_file(self, file_id: str) -> None:
        response = requests.delete(
            f"{FILE_MANAGEMENT_API_URL}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fileId": file_id}),
        )
        if response.status_code != 200 or response.json().get("deleted") is not True:
            logger.error(
                f"Failed to delete file {file_id}",
                status_code=response.status_code,
                response=response.text,
            )

    async def _revert_uploads(self, file_ids: list[str]) -> None:
        for file_id in file_ids:
            await self._delete_stored_file(file_id)
            await get_storage().delete_file(file_id)

    def _get_file_path_expiration(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=self.FILE_PATH_EXPIRES_IN)

    def _file_path_is_expired(self, file: UploadedFile) -> bool:
        expiration = file.file_path_expiration
        return expiration and expiration < datetime.now(timezone.utc) + timedelta(
            seconds=self.FILE_PATH_EXPIRATION_BUFFER
        )

    async def _upload(
        self,
        file_id: str,
        file: UploadFile,
        owner: Union[Agent, Thread],
        embedded: bool,
    ) -> UploadedFile:
        await self._validate_file_uniqueness(file, owner)
        blob = convert_to_blob(file)
        file_hash = await self._store(blob, file_id)
        file_path = self._get_presigned_url(file_id, file.filename)
        return await get_storage().put_file_owner(
            file_id,
            file_path,
            file.filename,
            file_hash,
            embedded,
            EmbeddingStatus.PENDING if embedded else None,
            owner,
            self._get_file_path_expiration(),
        )

    async def upload(
        self, files: list[UploadFileRequest], owner: Union[Agent, Thread]
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            embedded = (
                f.embedded if f.embedded is not None else self._is_embeddable(f.file)
            )
            try:
                uploaded_file = await self._upload(file_id, f.file, owner, embedded)
            except Exception as e:
                logger.exception(f"Failed to upload file {f.file.filename}")
                await self._revert_uploads(
                    [file_id] + [file.file_id for file in uploaded_files]
                )
                raise e
            uploaded_files.append(uploaded_file)
        return uploaded_files

    async def delete(self, file_id: str) -> None:
        await self._delete_stored_file(file_id)
        self._delete_embeddings(file_id)
        await get_storage().delete_file(file_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        storage = get_storage()
        ret = []
        for file in files:
            if self._file_path_is_expired(file):
                refreshed_file_path = self._get_presigned_url(
                    file.file_id, file.file_ref
                )
                updated_file = await storage.update_file_retrieve_information(
                    file.file_id,
                    file_path=refreshed_file_path,
                    file_path_expiration=self._get_file_path_expiration(),
                )
                ret.append(updated_file)
            else:
                ret.append(file)
        return ret

    async def read_file_contents(self, file_id: str) -> bytes:
        file = await get_storage().get_file_by_id(file_id)
        if not file:
            raise Exception(f"File not found: {file_id}")

        file_path = file.file_path
        if self._file_path_is_expired(file):
            updated_files = await self.refresh_file_paths([file])
            file_path = updated_files[0].file_path
        try:
            response = requests.get(file_path)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.exception(f"Failed to download file {file_id}: {str(e)}")
            raise e

    async def request_remote_file_upload(
        self, thread: Thread, file_name: str
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        file_ref = await self.generate_unique_file_ref(thread, file_name)
        presigned_post = self._get_presigned_post(file_id)
        return RemoteFileUploadData(
            url=presigned_post["url"],
            form_data=presigned_post["form_data"],
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self, thread: Thread, file_ref: str, file_id: str
    ) -> UploadedFile:
        file = await get_storage().put_file_owner(
            file_id=file_id,
            file_path=None,
            file_ref=file_ref,
            file_hash=get_hash(b""),
            embedded=False,
            embedding_status=None,
            owner=thread,
            file_path_expiration=datetime.now(timezone.utc),
        )
        return file
