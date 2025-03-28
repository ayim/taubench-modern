import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import structlog
from fastapi import UploadFile

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.files import FileData, UploadedFile, UploadFileRequest
from agent_server_types_v2.thread import Thread
from sema4ai_agent_server.constants import Constants
from sema4ai_agent_server.file_manager.v2.base_v2 import (
    MISSING_FILE_HASH,
    BaseFileManagerV2,
    RemoteFileUploadData,
    get_hash,
)
from sema4ai_agent_server.file_manager.v2.utils import (
    IS_WIN,
    convert_to_file_data,
    normalize_drive,
    url_to_fs_path,
)
from sema4ai_agent_server.storage.v2.option_v2 import get_storage_v2

logger = structlog.get_logger(__name__)


class LocalFileManagerV2(BaseFileManagerV2):
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
        owner: Agent | Thread,
        user_id: str,
        uploads: list[tuple[str, str]],
    ) -> None:
        """uploads is a list of tuples of the form (file_id, file_path)"""
        for file_id, file_url in uploads:
            await get_storage_v2().delete_file_v2(owner, file_id, user_id)

    async def _upload_files(
        self,
        files: list[UploadFileRequest],
        owner: Agent | Thread,
        user_id: str,
    ) -> list[UploadedFile]:
        """Uploads all files or none to ensure consistency."""
        owner_id = owner.id if isinstance(owner, Agent) else owner.thread_id
        logger.info(f"Uploading {len(files)} files to {owner_id}")

        uploaded_files: list[UploadedFile] = []
        for f in files:
            file_id = str(uuid4())
            assert f.file.filename, (
                "Invalid (empty) file name (should've raised an error in self._validate_files_pre_upload already)."
            )
            file_url = self._build_file_url(file_id, f.file.filename)
            try:
                file_data = convert_to_file_data(f.file)
                file_hash = await self._store(file_data, file_url)
                uploaded_file = await get_storage_v2().put_file_owner_v2(
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
                    f"Failed to upload {f.file.filename} with file id {file_id}. Error: {e}. Reverting all uploads.",
                )
                await self._revert_uploads(
                    owner,
                    user_id,
                    [(file.file_id, file.file_path) for file in uploaded_files],
                )
                raise e
        return uploaded_files

    async def delete(self, thread_id: str, user_id: str, file_id: str) -> None:
        # TODO: embeddings
        # await self._delete_embeddings(file_id)
        owner = await get_storage_v2().get_thread_v2(user_id, thread_id)
        await get_storage_v2().delete_file_v2(owner, file_id, user_id)

    async def delete_thread_files(self, thread_id: str, user_id: str) -> None:
        """Delete all files associated with a thread."""
        await get_storage_v2().delete_thread_files_v2(thread_id, user_id)

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        """Paths are not presigned in local storage"""
        raise NotImplementedError(
            "Local file manager does not support refreshing file paths",
        )

    async def read_file_contents(self, file_id: str, user_id: str) -> bytes:
        file = await get_storage_v2().get_file_by_id_v2(file_id, user_id)
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

    def _build_file_url(self, file_id: str, file_ref: str) -> str:
        """Returns the file URI for a given path.
        Will handle UNC paths and normalize windows drive letters to lower-case.

        Returns a URI in the format:
            - UNC path: file://shares/c$/far/boo
            - Windows drive letter: file:///c:/far/boo
            - Regular path: file:///path/to/file
        """
        abs_path = Path(Constants.UPLOAD_DIR).joinpath(file_id, file_ref)
        if IS_WIN:
            abs_path = Path(normalize_drive(str(abs_path)))
        return abs_path.as_uri()

    async def request_remote_file_upload(
        self,
        thread: Thread,
        file_name: str,
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        self._validate_files_pre_upload(
            [
                file_name,
            ],
        )
        file_ref = await self.generate_unique_file_ref(thread, file_name)
        url = self._build_file_url(file_id, file_ref)
        return RemoteFileUploadData(
            url=url,
            form_data={},
            file_id=file_id,
            file_ref=file_ref,
        )

    async def confirm_remote_file_upload(
        self,
        thread: Thread,
        file_ref: str,
        file_id: str,
    ) -> UploadedFile:
        file = await get_storage_v2().put_file_owner_v2(
            file_id=file_id,
            file_path=self._build_file_url(file_id, file_ref),
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            file_size_raw=0,
            mime_type=None,
            user_id=thread.user_id,
            embedded=False,
            embedding_status=None,
            owner=thread,
            file_path_expiration=None,
        )
        return file

    async def generate_unique_file_ref(
        self,
        owner: Agent | Thread,
        file_name: str,
    ) -> str:
        from sema4ai_agent_server.storage.v2.errors_v2 import UniqueFileRefError

        uploaded_file = await get_storage_v2().get_file_by_ref_v2(
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
