import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import requests
import structlog
from fastapi import status

from agent_platform.core.agent import Agent
from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.types import Scenario
from agent_platform.core.files import FileData, UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread import Thread
from agent_platform.core.work_items import WorkItem
from agent_platform.server.constants import WORK_ITEMS_SYSTEM_USER_SUB
from agent_platform.server.file_manager.base import (
    MISSING_FILE_HASH,
    BaseFileManager,
    RemoteFileUploadData,
    get_hash,
)
from agent_platform.server.file_manager.utils import convert_to_file_data

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CloudFileMgrConfig(Configuration):
    file_management_api_url: str = field(
        default="http://localhost",
        metadata=FieldMetadata(
            description="The URL of the file management API when using the cloud file manager.",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_FILE_MANAGEMENT_API_URL",
                "FILE_MANAGEMENT_API_URL",
            ],
        ),
    )
    file_path_expiration: int = field(
        default=43200,
        metadata=FieldMetadata(
            description="The expiration time of the file path in seconds, defaults to 12 hours.",
            env_vars=["SEMA4AI_AGENT_SERVER_FILE_PATH_EXPIRATION"],
        ),
    )
    file_path_expiration_buffer: int = field(
        default=300,
        metadata=FieldMetadata(
            description="The buffer time of the file path in seconds, defaults to 5 minutes.",
            env_vars=["SEMA4AI_AGENT_SERVER_FILE_PATH_EXPIRATION_BUFFER"],
        ),
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate that file_management_api_url is a valid URL
        try:
            parsed_url = urlparse(self.file_management_api_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError(
                    f"Invalid file_management_api_url: {self.file_management_api_url}. "
                    "URL must include scheme (http:// or https://) and host.",
                )
        except Exception as e:
            raise ValueError(
                f"Invalid file_management_api_url: {self.file_management_api_url}. {e!s}",
            ) from e


class CloudFileManager(BaseFileManager):
    def _get_presigned_post(self, file_id: str) -> dict:
        response = requests.post(
            f"{CloudFileMgrConfig.file_management_api_url}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fileId": file_id, "expiresIn": 300}),
        )
        return response.json()

    def _get_presigned_url(self, file_id: str, file_name: str) -> str:
        response = requests.get(
            f"{CloudFileMgrConfig.file_management_api_url}",
            headers={"Content-Type": "application/json"},
            params={
                "fileId": file_id,
                "expiresIn": CloudFileMgrConfig.file_path_expiration,
                "fileName": file_name,
            },
        )
        if response.status_code != status.HTTP_200_OK:
            logger.error(
                "Failed to get presigned URL. Received status_code=%s, expected=200.",
                response.status_code,
            )
            if response.status_code == status.HTTP_404_NOT_FOUND:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    status_code=response.status_code,
                    message="File not found in cloud storage",
                )
            raise PlatformHTTPError(
                error_code=ErrorCode.UNEXPECTED,
                status_code=response.status_code,
                message="Failed to get presigned URL",
            )

        return response.json()["url"]

    async def _store(self, file_data: FileData, file_id: str) -> str:
        presigned_post = self._get_presigned_post(file_id)
        method = presigned_post["method"]
        url = presigned_post["url"]
        headers = presigned_post.get("headers", {})
        fields = presigned_post.get("fields", {})

        logger.info(f"Upload file '{file_id}' to cloud storage: {method} {url}")

        if method == "PUT":
            has_content_type = any(k.lower() == "content-type" for k in headers.keys())
            if not has_content_type:
                # Needed because the current implementation is not (and should) sending
                # the mime-type when requesting the presigned url
                headers["content-type"] = file_data.mime_type

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=file_data.content,
            )
        elif method == "POST":
            # POST with form data
            # Check: https://requests.readthedocs.io/en/latest/user/quickstart/#post-a-multipart-encoded-file
            response = requests.post(
                url,
                headers=headers,
                data=fields,
                files={"file": (file_data.file_name, file_data.content, file_data.mime_type)},
            )
        else:
            raise Exception(f"Failed to upload file: Invalid method: {method}")

        if response.status_code not in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_204_NO_CONTENT,
        ):
            logger.error(
                "Failed to upload file. Received status_code=%s, expected=200 or 204.",
                response.status_code,
            )
            raise Exception("Failed to upload file")

        return get_hash(file_data.content)

    async def _upload_files(
        self,
        files: list[UploadFilePayload],
        owner: Agent | Thread | WorkItem | Scenario,
        user_id: str,
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            if not f.file.filename:
                raise ValueError("File name is required")
            try:
                file_data = convert_to_file_data(f.file)
                file_hash = await self._store(file_data, file_id)
                file_path = self._get_presigned_url(file_id, f.file.filename)
                uploaded_file = await self.storage.put_file_owner(
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
            f"{CloudFileMgrConfig.file_management_api_url}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"fileId": file_id}),
        )
        if response.status_code != status.HTTP_200_OK or (response.json().get("deleted") is not True):
            logger.error(
                f"Failed to delete file {file_id}",
                status_code=response.status_code,
                response=response.text,
            )

    async def _revert_uploads(
        self,
        file_ids: list[str],
        owner: Agent | Thread | WorkItem | Scenario,
    ) -> None:
        """Revert uploads by deleting files from both storage and cloud.

        Args:
            file_ids: List of file IDs to delete
            owner: The owner (Agent or Thread) of the files
        """
        for file_id in file_ids:
            try:
                # First try to delete from storage to validate existence
                await self.storage.delete_file(owner, file_id, owner.user_id)
                # Only delete from cloud if it exists in storage
                await self._delete_stored_file(file_id)
            except Exception as e:
                # Log but continue with other files
                logger.warning(f"Failed to revert upload for file {file_id}: {e}")

    def _get_file_path_expiration(self) -> datetime:
        return datetime.now(UTC) + timedelta(
            seconds=CloudFileMgrConfig.file_path_expiration,
        )

    async def delete(self, thread_id: str, user_id: str, file_id: str) -> None:
        await self._delete_stored_file(file_id)
        owner = await self.storage.get_thread(user_id, thread_id)
        await self.storage.delete_file(owner, file_id, user_id)

    async def delete_thread_files(self, thread_id: str, user_id: str) -> None:
        files = await self.storage.get_thread_files(thread_id, user_id)
        owner = await self.storage.get_thread(user_id, thread_id)
        for file in files:
            await self._delete_stored_file(file.file_id)
            await self.storage.delete_file(owner, file.file_id, user_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        ret = []
        for file in files:
            refreshed_file_path = self._get_presigned_url(
                file_id=file.file_id,
                file_name=file.file_ref,
            )
            updated_file = await self.storage.update_file_retrieve_information(
                file_id=file.file_id,
                file_path=refreshed_file_path,
                file_path_expiration=self._get_file_path_expiration(),
                user_id=file.user_id or "",  # TODO: fix?
            )
            ret.append(updated_file)

        return ret

    async def read_file_contents(self, file_id: str, user_id: str) -> bytes:
        file = await self.storage.get_file_by_id(file_id, user_id)
        if file is None:
            raise Exception(f"File not found: {file_id}")

        file_path = file.file_path
        if not file_path:
            raise Exception(f"File path for file {file_id} not available")

        updated_files = await self.refresh_file_paths([file])
        file_path = updated_files[0].file_path
        if not file_path:
            raise Exception(
                f"File path for file {file_id} not available after refreshing file paths",
            )

        try:
            response = requests.get(file_path)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.exception(f"Failed to download file {file_id}: {e!s}")
            raise e

    async def stream_file_contents(
        self,
        file_id: str,
        user_id: str,
        chunk_size: int = 8 * 1024,  # 8KB chunks by default
    ) -> AsyncGenerator[bytes, None]:
        """Stream file contents in chunks using an async generator.

        Args:
            file_id: The ID of the file to stream
            user_id: The ID of the user requesting the file
            chunk_size: The size of each chunk in bytes

        Yields:
            Chunks of the file content as bytes

        Raises:
            Exception: If the file is not found or cannot be accessed
        """
        file = await self.storage.get_file_by_id(file_id, user_id)
        if not file:
            raise Exception(f"File not found: {file_id}")

        file_path = file.file_path
        if not file_path:
            raise Exception(f"File path for file {file_id} not available")

        updated_files = await self.refresh_file_paths([file])
        file_path = updated_files[0].file_path
        if not file_path:
            raise Exception(
                f"File path for file {file_id} not available after refreshing file paths",
            )

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", file_path) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                        yield chunk
        except httpx.RequestError as e:
            logger.exception(f"Failed to stream file {file_id}: {e!s}")
            raise Exception(f"Failed to stream file: {e!s}") from e

    async def request_remote_file_upload(
        self,
        owner: Thread | WorkItem,
        file_name: str,
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        self._validate_files_pre_upload([file_name])
        file_ref = await self.generate_unique_file_ref(owner, file_name)
        presigned_post = self._get_presigned_post(file_id)
        return RemoteFileUploadData(
            url=presigned_post["url"],
            form_data=presigned_post["fields"],
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self,
        owner: Thread | WorkItem,
        file_ref: str,
        file_id: str,
    ) -> UploadedFile:
        if isinstance(owner, WorkItem):
            system_user, _ = await self.storage.get_or_create_user(WORK_ITEMS_SYSTEM_USER_SUB)
            user_id = system_user.user_id
        else:
            user_id = owner.user_id

        # Get the presigned download URL for the file
        refreshed_file_path = self._get_presigned_url(file_id, file_ref)

        file = await self.storage.put_file_owner(
            file_id=file_id,
            file_path=refreshed_file_path,
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            file_size_raw=0,
            mime_type="text/plain",
            user_id=user_id,
            embedded=False,
            embedding_status=None,
            owner=owner,
            file_path_expiration=self._get_file_path_expiration(),
        )
        return file

    async def generate_unique_file_ref(
        self,
        owner: Agent | Thread | WorkItem | Scenario,
        file_name: str,
    ) -> str:
        from agent_platform.server.storage.errors import UniqueFileRefError

        uploaded_file = await self.storage.get_file_by_ref(
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

    async def rm(self, *, file_id: str | None = None, file_path: str | None = None) -> None:
        if not file_id:
            raise ValueError("file_id is required for deleting files via CloudFileManager")

        await self._delete_stored_file(file_id)
