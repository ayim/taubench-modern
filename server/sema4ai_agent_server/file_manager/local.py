import os
import re
import sys
from pathlib import Path
from typing import Union
from urllib.parse import unquote, urlparse
from uuid import uuid4

import structlog
from fastapi import UploadFile

from sema4ai_agent_server.file_manager.base import (
    MISSING_FILE_HASH,
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


SEMA4AIDESKTOP_HOME = os.getenv("S4_AGENT_SERVER_HOME", ".")
UPLOAD_DIR = os.path.join(SEMA4AIDESKTOP_HOME, "uploads")


IS_WIN = sys.platform == "win32"
RE_DRIVE_LETTER_PATH = re.compile(r"^\/[a-zA-Z]:")


def normalize_drive(path: str) -> str:
    """Normalize windows drive letters to lowercase."""
    if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
        return path[0].lower() + path[1:]
    return path


class LocalFileManager(BaseFileManager):
    async def _store(self, blob: Blob, file_url: str) -> str:
        logger.info(f"Storing {file_url}")
        fs_path = self._url_to_fs_path(file_url)
        os.makedirs(os.path.dirname(fs_path), exist_ok=True)
        with open(fs_path, "wb") as f:
            f.write(blob.data)
        return get_hash(blob.data)

    async def _delete_stored_file(self, file_url: str) -> None:
        if not file_url:
            return
        logger.info(f"Deleting {file_url}")

        try:
            fs_path = self._url_to_fs_path(file_url)
            if os.path.exists(fs_path):
                os.remove(fs_path)
        except Exception as e:
            logger.exception(f"Error deleting file at {file_url}: {str(e)}")

    def _url_to_fs_path(self, file_url: str) -> str:
        """Returns the filesystem path of the given URI.
        Will handle UNC paths and normalize windows drive letters to lower-case.
        Also uses the platform specific path separator. Will *not* validate the
        path for invalid characters and semantics.
        Will validate the scheme of this URI.

        Examples:
            - UNC path: file://shares/c$/far/boo
            - Windows drive letter: file:///C:/far/boo
            - Regular path: file:///path/to/file
        """
        # scheme://netloc/path;parameters?query#fragment
        scheme, netloc, path, _params, _query, _fragment = urlparse(file_url)

        if scheme != "file":
            raise ValueError(f"Invalid file URL scheme: {file_url}")

        path = unquote(path)

        if netloc and path:
            # UNC path: file://shares/c$/far/boo
            value = f"//{netloc}{path}"

        elif RE_DRIVE_LETTER_PATH.match(path):
            # windows drive letter: file:///C:/far/boo
            value = path[1].lower() + path[2:]

        else:
            # Other path
            value = path

        if IS_WIN:
            value = value.replace("/", "\\")
            value = normalize_drive(value)

        return str(Path(value).resolve())

    async def _revert_uploads(self, uploads: list[tuple[str, str]]) -> None:
        """uploads is a list of tuples of the form (file_id, file_path)"""
        for file_id, file_url in uploads:
            await self._delete_stored_file(file_url)
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
            file_url = self._build_file_url(owner_id, file_id, f.file.filename)
            embedded = (
                f.embedded if f.embedded is not None else self._is_embeddable(f.file)
            )
            try:
                uploaded_file = await self._upload(
                    file_id, file_url, f.file, owner, embedded
                )
            except Exception as e:
                logger.exception(
                    f"Failed to upload {f.file.filename}. Reverting all uploads."
                )
                await self._revert_uploads(
                    [(file_id, file_url)]
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
            fs_path = self._url_to_fs_path(file.file_path)
            with open(fs_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.exception(f"File not found: {file.file_path}")
            raise

    def _build_file_url(self, owner_id: str, file_id: str, file_ref: str) -> str:
        """Returns the file URI for a given path.
        Will handle UNC paths and normalize windows drive letters to lower-case.

        Returns a URI in the format:
            - UNC path: file://shares/c$/far/boo
            - Windows drive letter: file:///c:/far/boo
            - Regular path: file:///path/to/file
        """
        abs_path = Path(UPLOAD_DIR).joinpath(owner_id, file_id, file_ref).resolve()
        if IS_WIN:
            abs_path = Path(normalize_drive(str(abs_path)))
        return abs_path.as_uri()

    async def request_remote_file_upload(
        self, thread: Thread, file_name: str
    ) -> RemoteFileUploadData:
        file_id = str(uuid4())
        file_ref = await self.generate_unique_file_ref(thread, file_name)
        url = self._build_file_url(thread.thread_id, file_id, file_ref)
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
            file_path=self._build_file_url(thread.thread_id, file_id, file_ref),
            file_ref=file_ref,
            file_hash=MISSING_FILE_HASH,
            embedded=False,
            embedding_status=None,
            owner=thread,
            file_path_expiration=None,
        )
        return file
