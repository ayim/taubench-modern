import hashlib
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

import structlog
from fastapi import HTTPException

from agent_platform.core.agent import Agent
from agent_platform.core.files import RemoteFileUploadData, UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread import Thread
from agent_platform.server.storage import BaseStorage

logger = structlog.get_logger(__name__)

NON_EMBEDDABLE_EXTENSIONS = {".csv", ".xls", ".xlsx", ".json", ".xml"}
MISSING_FILE_HASH = "SEMA4AI_MISSING_FILE_HASH"


class InvalidFileUploadError(HTTPException):
    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        super().__init__(status_code=400, detail=message)


class BaseFileManager(ABC):
    def __init__(self, storage: BaseStorage | None = None):
        self._storage = storage

    @property
    def storage(self) -> BaseStorage:
        if self._storage is None:
            raise ValueError("Storage is not set")
        return self._storage

    @storage.setter
    def storage(self, storage: BaseStorage) -> None:
        self._storage = storage

    async def upload(
        self,
        files: list[UploadFilePayload],
        owner: Thread,
        user_id: str,
    ) -> list[UploadedFile]:
        """Upload files and return their metadata."""
        if not files:
            raise InvalidFileUploadError("Files list cannot be empty")

        if any(not f.file.filename for f in files):
            raise InvalidFileUploadError("Invalid empty file name")

        # Use existing validation method
        self._validate_files_pre_upload(
            [f.file.filename for f in files if f.file.filename],
        )

        return await self._upload_files(files, owner, user_id)

    @abstractmethod
    async def _upload_files(
        self,
        files: list[UploadFilePayload],
        owner: Thread,
        user_id: str,
    ) -> list[UploadedFile]:
        """Implementation specific upload logic."""
        pass

    @abstractmethod
    async def delete(
        self,
        thread_id: str,
        user_id: str,
        file_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def delete_thread_files(
        self,
        thread_id: str,
        user_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def refresh_file_paths(
        self,
        files: list[UploadedFile],
    ) -> list[UploadedFile]:
        pass

    @abstractmethod
    async def read_file_contents(
        self,
        file_id: str,
        user_id: str,
    ) -> bytes:
        pass

    @abstractmethod
    def stream_file_contents(
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
        pass

    @abstractmethod
    async def request_remote_file_upload(
        self,
        thread: Thread,
        file_name: str,
    ) -> RemoteFileUploadData:
        pass

    @abstractmethod
    async def confirm_remote_file_upload(
        self,
        thread: Thread,
        file_ref: str,
        file_id: str,
    ) -> UploadedFile:
        pass

    def _validate_files_pre_upload(self, file_names: list[str]) -> None:
        # https://stackoverflow.com/questions/1976007/what-characters-are-forbidden-in-windows-and-linux-directory-names/31976060#31976060
        reserved_unix_file_names = {".", ".."}
        reserved_windows_file_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }

        if len(file_names) != len(set(file_names)):
            raise InvalidFileUploadError("File names must be unique")

        for filename in file_names:
            file_base, _ = os.path.splitext(filename)
            if (
                filename == ""
                or filename.upper() in reserved_windows_file_names
                or file_base.upper() in reserved_windows_file_names
                or filename in reserved_unix_file_names
            ):
                raise InvalidFileUploadError(f"Invalid file name: {filename}")

            # Check for invalid characters
            invalid_chars = '<>:"/\\|?*'
            if any(char in filename for char in invalid_chars):
                raise InvalidFileUploadError("Invalid file name")

    @abstractmethod
    async def generate_unique_file_ref(
        self,
        owner: Agent | Thread,
        file_name: str,
    ) -> str:
        pass

    # TODO: introduce this code once embedding support is added.
    # This code will be used / refactored once embedding support is added.

    # async def _delete_embeddings(self, file_id: str) -> None:
    #     await get_vector_store().adelete_by_file_id(file_id)

    # async def create_embeddings(self, file: UploadedFile, model: MODEL) -> None:
    #     owner_id = file.agent_id if file.agent_id else file.thread_id
    #     config = {
    #         "configurable": {
    #             "owner_id": owner_id,
    #             "file_id": file.file_id,
    #             "model": model,
    #         },
    #     }
    #     data = await self.read_file_contents(file.file_id)
    #     mimetype = guess_mimetype(file.file_ref, data)
    #     blob = Blob.from_data(data=data, path=file.file_ref, mime_type=mimetype)

    #     await get_storage().update_file_embedding_status(
    #         file.file_id, embedding_status=EmbeddingStatus.IN_PROGRESS,
    #     )
    #     try:
    #         await embed_runnable.ainvoke(blob, config)
    #     except Exception as e:
    #         logger.exception(f"Failed to embed file {file.file_ref}", exception=e)
    #         await get_storage().update_file_embedding_status(
    #             file.file_id, embedding_status=EmbeddingStatus.FAILURE,
    #         )
    #         raise e
    #     else:
    #         await get_storage().update_file_embedding_status(
    #             file.file_id, embedding_status=EmbeddingStatus.SUCCESS,
    #         )

    # async def create_missing_embeddings(
    #     self, model: MODEL, owner: Agent | Thread,
    # ) -> None:
    #     model_is_configured, _ = model.config.is_configured()
    #     if not model_is_configured:
    #         logger.info("Skipping creating file embeddings. Model is not configured.")
    #         return

    #     files = []
    #     if isinstance(owner, Agent):
    #         files = await get_storage().get_agent_files(owner.id)
    #     elif isinstance(owner, Thread):
    #         files = await get_storage().get_thread_files(owner.thread_id)

    #     for file in files:
    #         if file.embedded and file.embedding_status in (
    #             EmbeddingStatus.PENDING,
    #             EmbeddingStatus.FAILURE,
    #         ):
    #             logger.info(f"Creating embeddings for {file.file_ref}")
    #             try:
    #                 await self.create_embeddings(file, model)
    #             except Exception:
    #                 pass
    #         else:
    #             logger.info(
    #                 f"Skipping creating embeddings for {file.file_ref}. "
    #                 f"Should be embedded: {file.embedded}. "
    #                 f"Status: {file.embedding_status}.",
    #             )

    # def _is_embeddable(self, file: UploadFile) -> bool:
    #     file_extension = os.path.splitext(file.filename)[1].lower()
    #     return file_extension not in NON_EMBEDDABLE_EXTENSIONS


def get_hash(file_data: bytes) -> str:
    generated_hash = hashlib.sha256()
    generated_hash.update(file_data)
    return generated_hash.hexdigest()
