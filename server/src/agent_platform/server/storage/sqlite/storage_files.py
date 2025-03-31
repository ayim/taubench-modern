import os
from datetime import datetime
from sqlite3 import SQLITE_CONSTRAINT_UNIQUE, IntegrityError

from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.files import UploadedFile
from agent_platform.core.thread import Thread
from agent_platform.server.file_manager.utils import url_to_fs_path
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    ThreadFileNotFoundError,
    ThreadNotFoundError,
    UniqueFileRefError,
    UserPermissionError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageFilesMixin(CommonMixin):
    """
    Mixin providing SQLite-based file operations.
    Assumes that helper methods such as `_cursor()`
    and `_validate_uuid()` are available.
    """

    _logger = get_logger(__name__)

    async def _validate_owner_type(self, owner) -> tuple[str, str | None]:
        """Validate and return agent_id and optional thread_id from owner.

        Args:
            owner: Either an Agent or Thread instance

        Returns:
            tuple[str, str | None]: (agent_id, thread_id) where
                thread_id is None for Agent owners

        Raises:
            ValueError: If owner is neither Agent nor Thread
            AgentNotFoundError: If the referenced agent doesn't exist
            ThreadNotFoundError: If the referenced thread doesn't exist
        """
        self._logger.debug(f"Validating owner type {owner}")

        if not isinstance(owner, Agent | Thread):
            raise ValueError("Owner must be either Agent or Thread instance")

        # Common validation for both types
        self._validate_uuid(owner.agent_id)
        self._logger.debug(f"Validating agent {owner.agent_id}")
        await self._validate_agent_exists(owner.user_id, owner.agent_id)
        self._logger.debug(f"Agent {owner.agent_id} exists")
        if isinstance(owner, Agent):
            self._logger.debug("Owner is Agent", agent_id=owner.agent_id)
            return owner.agent_id, None

        # Handle Thread case
        self._validate_uuid(owner.thread_id)
        self._logger.debug(
            "Owner is Thread",
            thread_id=owner.thread_id,
            agent_id=owner.agent_id,
        )

        try:
            await self.get_thread(owner.user_id, owner.thread_id)
        except ThreadNotFoundError:
            raise ThreadNotFoundError(f"Thread {owner.thread_id} not found") from None

        return owner.agent_id, owner.thread_id

    async def _validate_agent_exists(self, user_id: str, agent_id: str) -> None:
        """Helper method to validate agent existence."""
        try:
            await self.get_agent(user_id, agent_id)
        except AgentNotFoundError:
            raise AgentNotFoundError(f"Agent {agent_id} not found") from None

    def _delete_stored_file(self, file_url: str) -> None:
        if not file_url:
            return
        self._logger.debug(f"Deleting {file_url}")

        try:
            fs_path = url_to_fs_path(file_url)
            if os.path.exists(fs_path):
                os.remove(fs_path)
                # remove parent directory as that gets
                # created by the file upload as well
                os.rmdir(os.path.dirname(fs_path))
        except Exception as e:
            self._logger.exception(f"Error deleting file at {file_url}: {e!s}")

    async def get_thread_files(
        self,
        thread_id: str,
        user_id: str,
    ) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        self._validate_uuid(thread_id)
        self._validate_uuid(user_id)
        self._logger.debug(
            "Getting all files for thread",
            thread_id=thread_id,
            user_id=user_id,
        )
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    f.*,
                    v2_check_user_access(f.user_id, :user_id) AS has_access
                FROM v2_file_owner f
                WHERE f.thread_id = :thread_id
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
            rows = await cur.fetchall()
            self._logger.debug(f"Found {len(list(rows))} files for thread {thread_id}")
            if not all(row["has_access"] for row in rows):
                raise UserPermissionError(
                    "User does not have access to one or more files",
                )
            # remove has_access from the rows
            rows = [
                {k: v for k, v in dict(row).items() if k != "has_access"}
                for row in rows
            ]
            if not rows:
                raise ThreadFileNotFoundError(f"No files found for thread {thread_id}")

            return [UploadedFile.model_validate(row_dict) for row_dict in rows]

    async def get_file_by_ref(
        self,
        owner: Agent | Thread,
        file_ref: str,
        user_id: str,
    ) -> UploadedFile | None:
        """Get a file by ref."""
        agent_id, thread_id = await self._validate_owner_type(owner)
        self._logger.debug(
            "Getting file by ref",
            file_ref=file_ref,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT f.*,
                    v2_check_user_access(f.user_id, :user_id) AS has_access
                FROM v2_file_owner f
                WHERE file_ref = :file_ref AND (
                  agent_id = :agent_id OR thread_id = :thread_id
                )
                """,
                {
                    "file_ref": file_ref,
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                },
            )
            row = await cur.fetchone()
            if row and not row["has_access"]:
                raise UserPermissionError("User does not have access to this file")
            if row:
                row = {k: v for k, v in dict(row).items() if k != "has_access"}
        self._logger.debug("File by ref result", found=bool(row))
        return UploadedFile.model_validate(dict(row)) if row else None

    async def get_file_by_id(
        self,
        file_id: str,
        user_id: str,
    ) -> UploadedFile | None:
        """Get a file by ID."""
        self._validate_uuid(file_id)
        self._validate_uuid(user_id)
        self._logger.debug("Getting file by ID", file_id=file_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT f.*,
                    v2_check_user_access(f.user_id, :user_id) AS has_access
                FROM v2_file_owner f
                WHERE file_id = :file_id
                """,
                {"file_id": file_id, "user_id": user_id},
            )
            row = await cur.fetchone()
            if row and not row["has_access"]:
                raise UserPermissionError("User does not have access to this file")
            if row:
                row = {k: v for k, v in dict(row).items() if k != "has_access"}
        self._logger.debug("File by ID result", found=bool(row))
        return UploadedFile.model_validate(dict(row)) if row else None

    async def delete_file(
        self,
        owner: Agent | Thread,
        file_id: str,
        user_id: str,
    ) -> None:
        """Delete a file by ID."""
        self._validate_uuid(file_id)
        agent_id, thread_id = await self._validate_owner_type(owner)
        self._validate_uuid(user_id)
        self._logger.debug("Deleting file by ID", file_id=file_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT f.file_path,
                    v2_check_user_access(f.user_id, :user_id) AS has_access
                FROM v2_file_owner f
                WHERE file_id = :file_id AND (
                  agent_id = :agent_id OR thread_id = :thread_id
                )
                """,
                {
                    "file_id": file_id,
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                },
            )
            row = await cur.fetchone()
            if not row:
                self._logger.exception(f"File {file_id} not found")
                raise ThreadFileNotFoundError(f"File {file_id} not found")
            if not row["has_access"]:
                raise UserPermissionError("User does not have access to this file")

            if os.environ.get("S4_AGENT_SERVER_FILE_MANAGER_TYPE") == "local":
                file_url = row["file_path"]
                self._delete_stored_file(file_url)

            await cur.execute(
                """
                DELETE FROM v2_file_owner WHERE file_id = :file_id
                """,
                {"file_id": file_id},
            )

    async def delete_thread_files(self, thread_id: str, user_id: str) -> None:
        """Delete all files associated with a thread."""
        self._validate_uuid(thread_id)
        self._validate_uuid(user_id)
        self._logger.debug("Deleting all files for thread", thread_id=thread_id)
        owner = await self.get_thread(user_id, thread_id)
        # iterate over all files in the thread and delete them
        files = await self.get_thread_files(thread_id, user_id)
        for file in files:
            self._logger.debug(f"Deleting file {file.file_id}")
            await self.delete_file(owner, file.file_id, user_id)

    async def put_file_owner(  # noqa: PLR0913
        self,
        file_id: str,
        file_path: str | None,
        file_ref: str,
        file_hash: str,
        file_size_raw: int,
        mime_type: str,
        user_id: str,
        embedded: bool,
        embedding_status: None,  # TODO: add a new type for EmbeddingStatus
        owner: Agent | Thread,
        file_path_expiration: datetime | None,
    ) -> UploadedFile:
        """Add or update a file owner."""
        self._validate_uuid(file_id)
        agent_id, thread_id = await self._validate_owner_type(owner)
        self._logger.debug(
            "Putting file owner",
            file_id=file_id,
            file_ref=file_ref,
            agent_id=agent_id,
            thread_id=thread_id,
            mime_type=mime_type,
            file_size_raw=file_size_raw,
        )

        file_dict = {
            "file_id": file_id,
            "file_path": file_path,
            "file_ref": file_ref,
            "file_hash": file_hash,
            "file_size_raw": file_size_raw,
            "mime_type": mime_type,
            "user_id": user_id,
            "embedded": embedded,
            "agent_id": agent_id,
            "thread_id": thread_id,
            "file_path_expiration": file_path_expiration,
            "created_at": datetime.now().isoformat(),
        }

        async with self._cursor() as cur:
            try:
                # Try to insert/update the file
                await cur.execute(
                    """
                    INSERT INTO v2_file_owner (
                        file_id, file_path, file_ref, file_hash,
                        file_size_raw, mime_type, user_id, embedded,
                        agent_id, thread_id, file_path_expiration,
                        created_at
                    )
                    VALUES (
                        :file_id, :file_path, :file_ref, :file_hash,
                        :file_size_raw, :mime_type, :user_id, :embedded,
                        :agent_id, :thread_id, :file_path_expiration,
                        :created_at
                    )
                    ON CONFLICT(file_id) DO UPDATE SET
                        file_path = excluded.file_path,
                        file_hash = excluded.file_hash,
                        file_size_raw = excluded.file_size_raw,
                        mime_type = excluded.mime_type,
                        embedded = excluded.embedded,
                        agent_id = excluded.agent_id,
                        thread_id = excluded.thread_id,
                        file_path_expiration = excluded.file_path_expiration,
                        created_at = excluded.created_at
                    """,
                    file_dict,
                )

            except IntegrityError as e:
                if e.sqlite_errorcode == SQLITE_CONSTRAINT_UNIQUE:
                    self._logger.exception("File already exists", file_ref=file_ref)
                    raise UniqueFileRefError(
                        file_ref,
                        detail=(
                            f"A file with the given file_ref {file_ref} already exists"
                        ),
                    ) from e
                else:
                    self._logger.exception(
                        "Database integrity error",
                        error=str(e),
                    )
                    raise
        self._logger.debug("File owner table modified", file_id=file_id)
        return UploadedFile.model_validate(file_dict)

    async def update_file_retrieve_information(
        self,
        file_id: str,
        file_path: str,
        file_path_expiration: datetime,
        user_id: str,
    ) -> UploadedFile:
        """Update file retrieval information."""
        self._validate_uuid(file_id)
        self._logger.debug(
            "Updating file retrieve information",
            file_id=file_id,
            file_path=file_path,
        )

        async with self._cursor() as cur:
            # First check access
            await cur.execute(
                """
                SELECT v2_check_user_access(f.user_id, :user_id) AS has_access
                FROM v2_file_owner f
                WHERE file_id = :file_id
                """,
                {"file_id": file_id, "user_id": user_id},
            )
            row = await cur.fetchone()
            if not row:
                self._logger.error("File not found", file_id=file_id)
                raise ThreadFileNotFoundError(f"File {file_id} not found")
            if not row["has_access"]:
                raise UserPermissionError("User does not have access to this file")

            # Then perform the update
            await cur.execute(
                """
                UPDATE v2_file_owner
                SET file_path = :file_path,
                    file_path_expiration = :file_path_expiration
                WHERE file_id = :file_id
                RETURNING *
                """,
                {
                    "file_id": file_id,
                    "file_path": file_path,
                    "file_path_expiration": file_path_expiration,
                },
            )
            row = await cur.fetchone()
            if not row:
                self._logger.error("File not found", file_id=file_id)
                raise ThreadFileNotFoundError(f"File {file_id} not found")

            self._logger.debug("File retrieve information updated", file_id=file_id)
            return UploadedFile.model_validate(dict(row))
