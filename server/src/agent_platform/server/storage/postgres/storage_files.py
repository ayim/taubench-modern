import os
from datetime import UTC, datetime

from psycopg.errors import IntegrityError, UniqueViolation
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.files import UploadedFile
from agent_platform.core.thread import Thread
from agent_platform.core.work_items import WorkItem
from agent_platform.server.constants import SystemConfig
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    ThreadFileNotFoundError,
    ThreadNotFoundError,
    UserPermissionError,
    WorkItemFileNotFoundError,
    WorkItemNotFoundError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageFilesMixin(CursorMixin, CommonMixin):
    """
    Mixin providing PostgreSQL-based file operations.
    Assumes that helper methods such as `_cursor()`
    and `_validate_uuid()` are available.
    """

    _logger = get_logger(__name__)

    async def _validate_agent_thread_owner_type(self, owner) -> tuple[str, str | None]:
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

    async def _validate_work_item_owner_type(self, owner: WorkItem) -> str:
        self._validate_uuid(owner.work_item_id)
        self._logger.debug(f"Validating owner type {owner}")
        await self._validate_work_item_exists(owner.work_item_id)
        return owner.work_item_id

    async def _validate_agent_exists(self, user_id: str, agent_id: str) -> None:
        """Helper method to validate agent existence."""
        try:
            await self.get_agent(user_id, agent_id)
        except AgentNotFoundError:
            raise AgentNotFoundError(f"Agent {agent_id} not found") from None

    async def _validate_work_item_exists(self, work_item_id: str) -> None:
        try:
            await self.get_work_item(work_item_id)
        except WorkItemNotFoundError:
            raise WorkItemNotFoundError(f"Work item {work_item_id} not found") from None

    def _delete_stored_file(self, file_url: str) -> None:
        # TODO: @kylie-bee: We need to separate concerns here, file manager should
        # handle file operations, not storage. They need to work together, but
        # they should have separate concerns. For now, this is a quick fix.
        from agent_platform.server.file_manager import url_to_fs_path

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
                """SELECT f.*,
                   v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                   FROM v2."file_owner" f
                   WHERE f.thread_id = %(thread_id)s::uuid
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
            rows = await cur.fetchall()
            self._logger.debug(f"Found {len(rows)} files for thread {thread_id}")
            if not all(row["has_access"] for row in rows):
                raise UserPermissionError(
                    "User does not have access to one or more files",
                )
            # remove has_access from the rows
            rows = [{k: v for k, v in dict(row).items() if k != "has_access"} for row in rows]
            return [UploadedFile.model_validate(row_dict) for row_dict in rows]

    async def get_file_by_ref(
        self,
        owner: Agent | Thread | WorkItem,
        file_ref: str,
        user_id: str,
    ) -> UploadedFile | None:
        """Get a file by ref."""
        match owner:
            case Agent() | Thread():
                agent_id, thread_id = await self._validate_agent_thread_owner_type(owner)
                work_item_id = None
                if not thread_id:
                    raise ValueError("Thread ID is required to fetch a file")
            case WorkItem():
                agent_id, thread_id = None, None
                work_item_id = await self._validate_work_item_owner_type(owner)
            case _:
                raise ValueError("Owner must be either Agent, Thread or WorkItem instance")

        self._logger.debug(
            "Getting file by ref",
            file_ref=file_ref,
            agent_id=agent_id,
            thread_id=thread_id,
        )

        async with self._cursor() as cur:
            if thread_id:
                await cur.execute(
                    """SELECT f.*,
                       v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                       FROM v2.file_owner f
                       WHERE file_ref = %(file_ref)s AND thread_id = %(thread_id)s::uuid
                    """,
                    {
                        "file_ref": file_ref,
                        "thread_id": thread_id,
                        "user_id": user_id,
                    },
                )
            elif work_item_id:
                await cur.execute(
                    """SELECT f.*,
                              v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                       FROM v2.file_owner f
                       WHERE file_ref = %(file_ref)s
                         AND work_item_id = %(work_item_id)s::uuid
                    """,
                    {
                        "file_ref": file_ref,
                        "work_item_id": work_item_id,
                        "user_id": user_id,
                    },
                )
            else:
                raise ValueError("Either thread_id or work_item_id must be provided")

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
        self._logger.debug("Getting file by ID", file_id=file_id, user_id=user_id)
        async with self._cursor() as cur:
            await cur.execute(
                """SELECT f.*,
                   v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                   FROM v2.file_owner f
                   WHERE file_id = %(file_id)s
                """,
                {
                    "file_id": file_id,
                    "user_id": user_id,
                },
            )
            row = await cur.fetchone()
            if row and not row["has_access"]:
                raise UserPermissionError("User does not have access to this file")
            if row:
                row = {k: v for k, v in dict(row).items() if k != "has_access"}
        self._logger.debug("File by ID result", found=bool(row))
        return UploadedFile.model_validate(dict(row)) if row else None

    async def _get_file_for_deletion(
        self,
        cur,
        file_id: str,
        user_id: str,
        thread_id: str | None,
        work_item_id: str | None,
    ) -> dict:
        """Get file information for deletion with access check."""
        if thread_id:
            await cur.execute(
                """SELECT f.file_path,
                   v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                   FROM v2.file_owner f
                   WHERE file_id = %(file_id)s AND thread_id = %(thread_id)s::uuid
                """,
                {"file_id": file_id, "thread_id": thread_id, "user_id": user_id},
            )
        elif work_item_id:
            await cur.execute(
                """SELECT f.file_path,
                          v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                   FROM v2.file_owner f
                   WHERE file_id = %(file_id)s AND work_item_id = %(work_item_id)s::uuid
                """,
                {"file_id": file_id, "work_item_id": work_item_id, "user_id": user_id},
            )
        else:
            raise ValueError("Either thread_id or work_item_id must be provided")

        row = await cur.fetchone()
        if not row:
            self._logger.error(f"File {file_id} not found")
            if thread_id:
                raise ThreadFileNotFoundError(f"File {file_id} not found")
            else:
                raise WorkItemFileNotFoundError(f"File {file_id} not found")

        if not row["has_access"]:
            raise UserPermissionError("User does not have access to this file")

        return row

    async def delete_file(
        self,
        owner: Agent | Thread | WorkItem,
        file_id: str,
        user_id: str,
    ) -> None:
        """Delete a file by ID."""
        self._validate_uuid(file_id)
        self._validate_uuid(user_id)
        match owner:
            case Agent() | Thread():
                agent_id, thread_id = await self._validate_agent_thread_owner_type(owner)
                work_item_id = None
                if not thread_id:
                    raise ValueError("Thread ID is required to delete a file")
            case WorkItem():
                _, thread_id = None, None
                work_item_id = await self._validate_work_item_owner_type(owner)
            case _:
                raise ValueError("Owner must be either Agent, Thread or WorkItem instance")

        self._logger.debug("Deleting file by ID", file_id=file_id)
        async with self._cursor() as cur:
            row = await self._get_file_for_deletion(cur, file_id, user_id, thread_id, work_item_id)

            if SystemConfig.file_manager_type == "local":
                file_url = row["file_path"]
                self._delete_stored_file(file_url)

            await cur.execute(
                """
                DELETE FROM v2.file_owner WHERE file_id = %(file_id)s
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
        owner: Agent | Thread | WorkItem,
        file_path_expiration: datetime | None,
    ) -> UploadedFile:
        """Add or update a file owner."""
        self._validate_uuid(file_id)

        file_dict = {
            "file_id": file_id,
            "file_path": file_path,
            "file_ref": file_ref,
            "file_hash": file_hash,
            "file_size_raw": file_size_raw,
            "mime_type": mime_type,
            "user_id": user_id,
            "embedded": embedded,
            "file_path_expiration": file_path_expiration,
            "created_at": datetime.now(UTC).isoformat(),
        }

        match owner:
            case Agent() | Thread():
                agent_id, thread_id = await self._validate_agent_thread_owner_type(owner)
                work_item_id = None
                file_dict |= {"agent_id": agent_id, "thread_id": thread_id, "work_item_id": None}
            case WorkItem():
                work_item_id = await self._validate_work_item_owner_type(owner)
                agent_id, thread_id = None, None
                file_dict |= {"agent_id": None, "thread_id": None, "work_item_id": work_item_id}
            case _:
                raise ValueError("Owner must be either Agent, Thread or WorkItem instance")

        self._logger.debug(
            "Putting file owner",
            file_id=file_id,
            file_ref=file_ref,
            agent_id=agent_id,
            thread_id=thread_id,
            mime_type=mime_type,
            work_item_id=work_item_id,
            file_size_raw=file_size_raw,
        )

        async with self._cursor() as cur:
            try:
                await cur.execute("SAVEPOINT savepoint1")
                # Try to insert/update the file
                await cur.execute(
                    """
                    INSERT INTO v2.file_owner (
                        file_id, file_path, file_ref, file_hash,
                        file_size_raw, mime_type, user_id, embedded,
                        agent_id, thread_id, work_item_id, file_path_expiration,
                        created_at
                    )
                    VALUES (
                        %(file_id)s, %(file_path)s, %(file_ref)s, %(file_hash)s,
                        %(file_size_raw)s, %(mime_type)s, %(user_id)s::uuid,
                        %(embedded)s, %(agent_id)s::uuid, %(thread_id)s::uuid,
                        %(work_item_id)s::uuid,
                        %(file_path_expiration)s, %(created_at)s
                    )
                    ON CONFLICT(file_id) DO UPDATE SET
                        file_path = EXCLUDED.file_path,
                        file_ref = EXCLUDED.file_ref,
                        file_hash = EXCLUDED.file_hash,
                        file_size_raw = EXCLUDED.file_size_raw,
                        mime_type = EXCLUDED.mime_type,
                        embedded = EXCLUDED.embedded,
                        agent_id = EXCLUDED.agent_id,
                        thread_id = EXCLUDED.thread_id,
                        work_item_id = EXCLUDED.work_item_id,
                        file_path_expiration = EXCLUDED.file_path_expiration,
                        created_at = EXCLUDED.created_at
                    """,
                    file_dict,
                )
            except UniqueViolation as e:
                self._logger.warning(
                    "Insert failed due to unique constraint violation", file_ref=file_ref
                )

                # Rollback to the savepoint so we can continue using this transaction
                await cur.execute("ROLLBACK TO SAVEPOINT savepoint1")

                # Check if the unique file_ref per thread constraint failed
                if "unique_file_ref_thread_v2" not in str(e):
                    raise e

                await cur.execute(
                    """
                    UPDATE v2.file_owner SET
                    file_id = %(file_id)s,
                    file_path = %(file_path)s,
                    file_hash = %(file_hash)s,
                    file_size_raw = %(file_size_raw)s,
                    mime_type = %(mime_type)s,
                    embedded = %(embedded)s,
                    agent_id = %(agent_id)s::uuid,
                    user_id = %(user_id)s::uuid,
                    file_path_expiration = %(file_path_expiration)s
                    WHERE file_ref = %(file_ref)s and thread_id = %(thread_id)s::uuid
                """,
                    file_dict,
                )
                # Fall through to outer return statement
            except IntegrityError as e:
                self._logger.exception(
                    "Database integrity error",
                    error=str(e),
                    pgcode=getattr(e, "pgcode", None),
                )
                raise
        self._logger.debug("File owner table modified", file_id=file_id)
        return UploadedFile.model_validate(file_dict)

    async def associate_work_item_file(
        self,
        file_id: str,
        work_item: WorkItem,
        agent_id: str,
        thread_id: str,
    ) -> None:
        """Associates an existing file with a agent_id and thread_id."""
        self._validate_uuid(file_id)
        self._validate_uuid(agent_id)
        self._validate_uuid(thread_id)
        self._logger.debug(
            "Associating workitem file with agent and thread",
            file_id=file_id,
            work_item_id=work_item.work_item_id,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        async with self._cursor() as cur:
            result = await cur.execute(
                """
                UPDATE v2.file_owner SET
                agent_id = %(agent_id)s::uuid,
                thread_id = %(thread_id)s::uuid
                WHERE file_id = %(file_id)s and work_item_id = %(work_item_id)s::uuid
                """,
                {
                    "file_id": file_id,
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "work_item_id": work_item.work_item_id,
                },
            )
            # Raise an error if we couldn't find this workitem and file pair.
            if result.rowcount == 0:
                self._logger.error("File not found", file_id=file_id)
                raise WorkItemFileNotFoundError(f"File {file_id} not found")
            elif result.rowcount > 1:
                self._logger.error("Multiple files found (should not happen)", file_id=file_id)
                raise Exception(f"Multiple files found for file {file_id} (should not happen)")

    async def update_file_retrieve_information(
        self,
        file_id: str,
        file_path: str,
        file_path_expiration: datetime,
        user_id: str,
    ) -> UploadedFile:
        """Update file retrieval information.

        Args:
            file_id: The ID of the file to update
            file_path: The new file path
            file_path_expiration: When the file path expires

        Returns:
            UploadedFile: The updated file information

        Raises:
            ThreadFileNotFoundError: If the file is not found
        """
        self._validate_uuid(file_id)
        self._logger.debug(
            "Updating file retrieve information",
            file_id=file_id,
            file_path=file_path,
        )

        async with self._cursor() as cur:
            # First check access
            # Nb. file_id contains a uuid4 value, but is a TEXT column in the database.
            await cur.execute(
                """
                SELECT v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                FROM v2.file_owner f
                WHERE file_id = %(file_id)s
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
                UPDATE v2.file_owner
                SET file_path = %(file_path)s,
                    file_path_expiration = %(file_path_expiration)s
                WHERE file_id = %(file_id)s
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

    async def get_workitem_files(self, work_item_id: str, user_id: str) -> list[UploadedFile]:
        """Get all files associated with a work item."""
        self._validate_uuid(work_item_id)
        self._logger.debug("Getting all files for work item", work_item_id=work_item_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT f.*, v2.check_user_access(f.user_id, %(user_id)s::uuid) AS has_access
                FROM v2.file_owner f
                WHERE f.work_item_id = %(work_item_id)s::uuid
                """,
                {"work_item_id": work_item_id, "user_id": user_id},
            )
            rows = await cur.fetchall()
            self._logger.debug(f"Found {len(rows)} files for work item {work_item_id}")
            if not all(row["has_access"] for row in rows):
                raise UserPermissionError(
                    "User does not have access to one or more files",
                )
            # remove has_access from the rows
            rows = [{k: v for k, v in dict(row).items() if k != "has_access"} for row in rows]
            return [UploadedFile.model_validate(row_dict) for row_dict in rows]
