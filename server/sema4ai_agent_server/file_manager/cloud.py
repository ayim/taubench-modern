import json
import os
from datetime import datetime, timedelta, timezone
from typing import Union
from uuid import uuid4

import requests
import structlog
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import BaseFileManager, get_hash
from sema4ai_agent_server.schema import Assistant, Thread, UploadedFile
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

    def _get_presigned_url(self, file_id: str, file_name: str) -> dict:
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

    async def _revert_upload(self, file_id: str) -> None:
        await self._delete_stored_file(file_id)
        self._delete_embeddings(file_id)
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
        owner: Union[Assistant, Thread],
    ) -> UploadedFile:
        await self._validate_file_uniqueness(file, owner)

        blob = convert_to_blob(file)
        file_hash = await self._store(blob, file_id)
        file_path = self._get_presigned_url(file_id, file.filename)

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
            self._get_file_path_expiration(),
        )

    async def upload(
        self,
        file: UploadFile,
        owner: Union[Assistant, Thread],
    ) -> UploadedFile:
        file_id = str(uuid4())
        try:
            return await self._upload(file_id, file, owner)
        except Exception as e:
            logger.exception(f"Failed to upload file {file.filename}")
            await self._revert_upload(file_id)
            raise e

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
                    file.file_id, file.file_name
                )
                updated_file = await storage.update_file(
                    file.file_id,
                    {
                        "file_path": refreshed_file_path,
                        "file_path_expiration": self._get_file_path_expiration(),
                    },
                )
                ret.append(updated_file)
            else:
                ret.append(file)
        return ret
