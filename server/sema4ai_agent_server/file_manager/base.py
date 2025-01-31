import hashlib
import os
from typing import Union

import structlog
from agent_server_types import MODEL, Agent, EmbeddingStatus, Thread, UploadedFile
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from sema4ai_agent_server.schema import UploadFileRequest
from sema4ai_agent_server.storage.embed import (
    Blob,
    embed_runnable,
    get_vector_store,
    guess_mimetype,
)
from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)

NON_EMBEDDABLE_EXTENSIONS = {".csv", ".xls", ".xlsx", ".json", ".xml"}
MISSING_FILE_HASH = "SEMA4AI_MISSING_FILE_HASH"


class InvalidFileUploadError(HTTPException):
    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        super().__init__(status_code=400, detail=message)


class RemoteFileUploadData(BaseModel):
    url: str
    form_data: dict
    file_id: str
    file_ref: str


class BaseFileManager:
    async def upload(
        self, files: list[UploadFileRequest], owner: Union[Agent, Thread]
    ) -> list[UploadedFile]:
        raise NotImplementedError()

    async def delete(self, file_id: str) -> None:
        raise NotImplementedError()

    async def refresh_file_paths(self, files: list[UploadedFile]) -> list[UploadedFile]:
        raise NotImplementedError()

    async def read_file_contents(self, file_id: str) -> bytes:
        raise NotImplementedError()

    async def _delete_embeddings(self, file_id: str) -> None:
        await get_vector_store().adelete_by_file_id(file_id)

    async def create_embeddings(self, file: UploadedFile, model: MODEL) -> None:
        owner_id = file.agent_id if file.agent_id else file.thread_id
        config = {
            "configurable": {
                "owner_id": owner_id,
                "file_id": file.file_id,
                "model": model,
            }
        }
        data = await self.read_file_contents(file.file_id)
        mimetype = guess_mimetype(file.file_ref, data)
        blob = Blob.from_data(data=data, path=file.file_ref, mime_type=mimetype)

        await get_storage().update_file_embedding_status(
            file.file_id, embedding_status=EmbeddingStatus.IN_PROGRESS
        )
        try:
            await embed_runnable.ainvoke(blob, config)
        except Exception as e:
            logger.exception(f"Failed to embed file {file.file_ref}", exception=e)
            await get_storage().update_file_embedding_status(
                file.file_id, embedding_status=EmbeddingStatus.FAILURE
            )
            raise e
        else:
            await get_storage().update_file_embedding_status(
                file.file_id, embedding_status=EmbeddingStatus.SUCCESS
            )

    async def create_missing_embeddings(
        self, model: MODEL, owner: Union[Agent, Thread]
    ) -> None:
        model_is_configured, _ = model.config.is_configured()
        if not model_is_configured:
            logger.info("Skipping creating file embeddings. Model is not configured.")
            return

        files = []
        if isinstance(owner, Agent):
            files = await get_storage().get_agent_files(owner.id)
        elif isinstance(owner, Thread):
            files = await get_storage().get_thread_files(owner.thread_id)

        for file in files:
            if file.embedded and file.embedding_status in (
                EmbeddingStatus.PENDING,
                EmbeddingStatus.FAILURE,
            ):
                logger.info(f"Creating embeddings for {file.file_ref}")
                try:
                    await self.create_embeddings(file, model)
                except Exception:
                    pass
            else:
                logger.info(
                    f"Skipping creating embeddings for {file.file_ref}. "
                    f"Should be embedded: {file.embedded}. "
                    f"Status: {file.embedding_status}."
                )

    def _is_embeddable(self, file: UploadFile) -> bool:
        file_extension = os.path.splitext(file.filename)[1].lower()
        return file_extension not in NON_EMBEDDABLE_EXTENSIONS

    def _validate_files_pre_upload(self, files: list[UploadFileRequest]) -> None:
        # https://stackoverflow.com/questions/1976007/what-characters-are-forbidden-in-windows-and-linux-directory-names/31976060#31976060
        FORBIDDEN_UNIX_CHARACTERS = {"/"}
        FORBIDDEN_WINDOWS_CHARACTERS = {"<", ">", ":", '"', "/", "\\", "|", "?", "*"}
        RESERVED_UNIX_FILE_NAMES = {".", ".."}
        RESERVED_WINDOWS_FILE_NAMES = {
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

        file_names = [f.file.filename for f in files]
        if len(file_names) != len(set(file_names)):
            raise InvalidFileUploadError("File names must be unique")

        for f in files:
            filename = f.file.filename or ""
            file_base, _ = os.path.splitext(filename)
            if (
                filename == ""
                or filename in RESERVED_WINDOWS_FILE_NAMES
                or file_base in RESERVED_WINDOWS_FILE_NAMES
                or filename in RESERVED_UNIX_FILE_NAMES
            ):
                raise InvalidFileUploadError(f"Invalid file name: {filename}")

            forbidden_chars = FORBIDDEN_UNIX_CHARACTERS | FORBIDDEN_WINDOWS_CHARACTERS
            if any(char in filename for char in forbidden_chars):
                raise InvalidFileUploadError(f"Invalid file name: {filename}")

    async def generate_unique_file_ref(
        self, owner: Union[Agent, Thread], file_name: str
    ) -> str:
        from sema4ai_agent_server.storage import UniqueFileRefError

        uploaded_file = await get_storage().get_file(owner, file_name)
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

    async def request_remote_file_upload(
        self, thread: Thread, file_name: str
    ) -> RemoteFileUploadData:
        raise NotImplementedError()

    async def confirm_remote_file_upload(
        self, thread: Thread, file_ref: str, file_id: str
    ) -> UploadedFile:
        raise NotImplementedError()


def get_hash(file_data: bytes) -> str:
    hash = hashlib.sha256()
    hash.update(file_data)
    return hash.hexdigest()
