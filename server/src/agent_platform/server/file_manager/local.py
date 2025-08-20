import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import structlog

from agent_platform.core.agent import Agent
from agent_platform.core.files import FileData, UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread import Thread
from agent_platform.core.work_items import WorkItem
from agent_platform.server.constants import SystemPaths
from agent_platform.server.file_manager.base import (
    MISSING_FILE_HASH,
    BaseFileManager,
    RemoteFileUploadData,
    get_hash,
)
from agent_platform.server.file_manager.utils import (
    IS_WIN,
    convert_to_file_data,
    normalize_drive,
    url_to_fs_path,
)

logger = structlog.get_logger(__name__)


class LocalFileManager(BaseFileManager):
    async def _store(self, file_data: FileData, file_url: str) -> str:
        logger.info(f"Storing {file_url}")
        fs_path = url_to_fs_path(file_url)
        os.makedirs(os.path.dirname(fs_path), exist_ok=True)
        file_data_as_bytes = file_data.content
        with open(fs_path, "wb") as f:
            f.write(file_data_as_bytes)
        return get_hash(file_data_as_bytes)

    async def _revert_uploads(
        self,
        owner: Agent | Thread | WorkItem,
        user_id: str,
        uploads: list[tuple[str, str]],
    ) -> None:
        """uploads is a list of tuples of the form (file_id, file_path)"""
        for file_id, _ in uploads:
            await self.storage.delete_file(owner, file_id, user_id)

    async def _upload_files(
        self,
        files: list[UploadFilePayload],
        owner: Agent | Thread | WorkItem,
        user_id: str,
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        match owner:
            case Agent():
                owner_id = owner.agent_id
            case Thread():
                owner_id = owner.thread_id
            case WorkItem():
                owner_id = owner.work_item_id
            case _:
                raise ValueError()

        # owner_id = owner.agent_id if isinstance(owner, Agent) else owner.thread_id
        logger.info(f"Uploading {len(files)} files to {owner_id}")
        logger.info(f"Owner: <{owner.__class__.__name__} id={owner_id}>")
        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            assert f.file.filename, (
                "Invalid (empty) file name (should've raised an error in "
                "self._validate_files_pre_upload already)."
            )
            file_url = self._build_file_url(file_id, f.file.filename)
            try:
                file_data = convert_to_file_data(f.file)
                file_hash = await self._store(file_data, file_url)
                uploaded_file = await self.storage.put_file_owner(
                    file_id,
                    file_url,
                    f.file.filename,
                    file_hash,
                    file_data.file_size,
                    file_data.mime_type,
                    user_id,
                    False,  # embedded
                    None,
                    owner,
                    file_path_expiration=None,
                )
                uploaded_files.append(uploaded_file)
            except Exception as e:
                logger.exception(
                    f"Failed to upload {f.file.filename} with file id {file_id}. "
                    f"Error: {e}. Reverting all uploads.",
                )
                await self._revert_uploads(
                    owner,
                    user_id,
                    [(file.file_id, file.file_path) for file in uploaded_files if file.file_path],
                )
                raise e
        return uploaded_files

    async def delete(self, thread_id: str, user_id: str, file_id: str) -> None:
        # TODO: embeddings
        # await self._delete_embeddings(file_id)
        owner = await self.storage.get_thread(user_id, thread_id)
        await self.storage.delete_file(owner, file_id, user_id)

    async def delete_thread_files(self, thread_id: str, user_id: str) -> None:
        """Delete all files associated with a thread."""
        await self.storage.delete_thread_files(thread_id, user_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        """Paths are not presigned in local storage"""
        return files

    async def read_file_contents(self, file_id: str, user_id: str) -> bytes:
        file = await self.storage.get_file_by_id(file_id, user_id)
        if not file:
            raise Exception(f"File not found: {file_id}")
        if not file.file_path:
            raise Exception(f"Unable to read file {file_id} (no file path).")
        try:
            fs_path = url_to_fs_path(file.file_path)
            with open(fs_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.exception(f"File not found: {file.file_path}")
            raise

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
        if not file.file_path:
            raise Exception(f"Unable to read file {file_id} (no file path).")

        try:
            fs_path = url_to_fs_path(file.file_path)
            with open(fs_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk
        except FileNotFoundError:
            logger.exception(f"File not found: {file.file_path}")
            raise

    def _build_file_url(self, file_id: str, file_ref: str) -> str:
        """Returns the file URI for a given path.
        Will handle UNC paths and normalize windows drive letters to lower-case.

        Returns a URI in the format:
            - UNC path: file://shares/c$/far/boo
            - Windows drive letter: file:///c:/far/boo
            - Regular path: file:///path/to/file
        """
        # Ensure we have an absolute path by resolving it
        abs_path = Path(SystemPaths.upload_dir).absolute().joinpath(file_id, file_ref)
        if IS_WIN:
            abs_path = Path(normalize_drive(str(abs_path)))
        return abs_path.as_uri()

    async def request_remote_file_upload(
        self,
        owner: Thread | WorkItem,
        file_name: str,
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        self._validate_files_pre_upload(
            [
                file_name,
            ],
        )
        file_ref = await self.generate_unique_file_ref(owner, file_name)
        url = self._build_file_url(file_id, file_ref)
        return RemoteFileUploadData(
            url=url,
            form_data={},
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self,
        owner: Thread | WorkItem,
        file_ref: str,
        file_id: str,
    ) -> UploadedFile:
        file = await self.storage.put_file_owner(
            file_id=file_id,
            file_path=self._build_file_url(file_id, file_ref),
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            file_size_raw=0,
            mime_type="text/plain",
            user_id=owner.user_id,
            embedded=False,
            embedding_status=None,
            owner=owner,
            file_path_expiration=None,
        )
        return file

    async def generate_unique_file_ref(
        self,
        owner: Agent | Thread | WorkItem,
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
        if not file_path:
            raise ValueError("file_path is required for deleting files via LocalFileManager")

        try:
            fs_path = url_to_fs_path(file_path)
            if os.path.exists(fs_path):
                os.remove(fs_path)
                # remove parent directory as that gets
                # created by the file upload as well
                os.rmdir(os.path.dirname(fs_path))
        except Exception as e:
            logger.exception(f"Error deleting file at {file_path}: {e!s}")
