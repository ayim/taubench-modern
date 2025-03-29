import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import requests
import structlog
from fastapi import status

from agent_platform.core.agent import Agent
from agent_platform.core.files import FileData, UploadedFile, UploadFileRequest
from agent_platform.core.thread import Thread
from agent_platform.server.file_manager.base import (
    MISSING_FILE_HASH,
    BaseFileManager,
    RemoteFileUploadData,
    get_hash,
)
from agent_platform.server.file_manager.utils import convert_to_file_data
from agent_platform.server.storage.option import get_storage

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

    async def _store(self, file_data: FileData, file_id: str) -> str:
        presigned_post = self._get_presigned_post(file_id)
        payload = presigned_post["form_data"]
        response = requests.post(
            presigned_post["url"],
            data=payload,
            files={"file": file_data.content},
        )
        if response.status_code != status.HTTP_200_OK:
            logger.error(
                "Failed to upload file",
                status_code=response.status_code,
            )
            raise Exception("Failed to upload file")

        return get_hash(file_data.content)

    async def _upload_files(
        self,
        files: list[UploadFileRequest],
        owner: Agent | Thread,
        user_id: str,
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            try:
                file_data = convert_to_file_data(f.file)
                file_hash = await self._store(file_data, file_id)
                file_path = self._get_presigned_url(file_id, f.file.filename)
                uploaded_file = await get_storage().put_file_owner(
                    file_id,
                    file_path,
                    f.file.filename,
                    file_hash,
                    file_data.file_size,
                    file_data.mime_type,
                    user_id,
                    False,  # embedded
                    None,
                    owner,
                    self._get_file_path_expiration(),
                )
                uploaded_files.append(uploaded_file)
            except Exception as e:
                logger.exception(f"Failed to upload file {f.file.filename}")
                await self._revert_uploads(
                    [file.file_id for file in uploaded_files],
                    owner,
                )
                raise e
        return uploaded_files

    async def _delete_stored_file(self, file_id: str) -> None:
        response = requests.delete(
            f"{FILE_MANAGEMENT_API_URL}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fileId": file_id}),
        )
        if response.status_code != status.HTTP_200_OK or (
            response.json().get("deleted") is not True
        ):
            logger.error(
                f"Failed to delete file {file_id}",
                status_code=response.status_code,
                response=response.text,
            )

    async def _revert_uploads(
        self,
        file_ids: list[str],
        owner: Agent | Thread,
    ) -> None:
        """Revert uploads by deleting files from both storage and cloud.

        Args:
            file_ids: List of file IDs to delete
            owner: The owner (Agent or Thread) of the files
        """
        for file_id in file_ids:
            try:
                # First try to delete from storage to validate existence
                await get_storage().delete_file(owner, file_id, owner.user_id)
                # Only delete from cloud if it exists in storage
                await self._delete_stored_file(file_id)
            except Exception as e:
                # Log but continue with other files
                logger.warning(f"Failed to revert upload for file {file_id}: {e}")

    def _get_file_path_expiration(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.FILE_PATH_EXPIRES_IN)

    def _file_path_is_expired(self, file: UploadedFile) -> bool:
        expiration = file.file_path_expiration
        return expiration and expiration < datetime.now(UTC) + timedelta(
            seconds=self.FILE_PATH_EXPIRATION_BUFFER,
        )

    async def delete(self, thread_id: str, user_id: str, file_id: str) -> None:
        await self._delete_stored_file(file_id)
        owner = await get_storage().get_thread(user_id, thread_id)
        await get_storage().delete_file(owner, file_id, user_id)

    async def delete_thread_files(self, thread_id: str, user_id: str) -> None:
        files = await get_storage().get_thread_files(thread_id, user_id)
        owner = await get_storage().get_thread(user_id, thread_id)
        for file in files:
            await self._delete_stored_file(file.file_id)
            await get_storage().delete_file(owner, file.file_id, user_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        storage = get_storage()
        ret = []
        for file in files:
            if self._file_path_is_expired(file):
                refreshed_file_path = self._get_presigned_url(
                    file_id=file.file_id,
                    file_name=file.file_ref,
                )
                updated_file = await storage.update_file_retrieve_information(
                    file_id=file.file_id,
                    file_path=refreshed_file_path,
                    file_path_expiration=self._get_file_path_expiration(),
                )
                ret.append(updated_file)
            else:
                ret.append(file)
        return ret

    async def read_file_contents(self, file_id: str, user_id: str) -> bytes:
        file = await get_storage().get_file_by_id(file_id, user_id)
        if not file:
            raise Exception(f"File not found: {file_id}")

        file_path = file.file_path
        if not file_path:
            raise Exception(f"File path for file {file_id} not available")

        if self._file_path_is_expired(file):
            updated_files = await self.refresh_file_paths([file])
            file_path = updated_files[0].file_path
            if not file_path:
                raise Exception(
                    f"File path for file {file_id} not available after "
                    "refreshing file paths",
                )

        try:
            response = requests.get(file_path)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.exception(f"Failed to download file {file_id}: {e!s}")
            raise e

    async def request_remote_file_upload(
        self,
        thread: Thread,
        file_name: str,
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        self._validate_files_pre_upload([file_name])
        file_ref = await self.generate_unique_file_ref(thread, file_name)
        presigned_post = self._get_presigned_post(file_id)
        return RemoteFileUploadData(
            url=presigned_post["url"],
            form_data=presigned_post["form_data"],
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self,
        thread: Thread,
        file_ref: str,
        file_id: str,
    ) -> UploadedFile:
        file = await get_storage().put_file_owner(
            file_id=file_id,
            file_path=None,
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            file_size_raw=0,
            mime_type=None,
            user_id=thread.user_id,
            embedded=False,
            embedding_status=None,
            owner=thread,
            file_path_expiration=datetime.now(UTC),
        )
        return file

    async def generate_unique_file_ref(
        self,
        owner: Agent | Thread,
        file_name: str,
    ) -> str:
        from agent_platform.server.storage.errors import UniqueFileRefError

        uploaded_file = await get_storage().get_file_by_ref(
            owner,
            file_name,
            owner.user_id,
        )
        if uploaded_file:
            # This file already exists, so, double check if it's already embedded.
            # If it is, we can't override it!
            if uploaded_file.embedded:
                raise UniqueFileRefError(file_name)

        # Just return the file name as it is (which may override an existing file)

        # Note: there is code in the repository to generate a unique file ref
        # with a rule such as `data (1).csv`, `data (2).csv`, etc.

        # This was changed because the usage of always creating a new file ref instead
        # of overriding files with the same name made it more difficult to manage
        # in actions (as actions are stateless, referencing a file by the same name is
        # easy, but keeping a track of which is the new name to reference if a file
        # is updated is not that straightforward).
        # In the future maybe we could have some other versioning scheme to access old
        # files, but for now, just overriding is simpler and easier to manage.

        return file_name
