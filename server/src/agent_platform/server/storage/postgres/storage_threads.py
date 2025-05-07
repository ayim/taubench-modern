from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ThreadNotFoundError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.postgres.storage_messages import (
    PostgresStorageMessagesMixin,
)


class PostgresStorageThreadsMixin(PostgresStorageMessagesMixin):
    """Mixin for PostgreSQL thread operations."""

    async def list_threads(self, user_id: str) -> list[Thread]:
        """List all threads for the given user."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)

        async with self._cursor() as cur:
            # 2. Get the threads (and check if the user has access)
            await cur.execute(
                """SELECT t.*
                   FROM v2.thread t
                   WHERE v2.check_user_access(t.user_id, %(user_id)s::uuid)""",
                {"user_id": user_id},
            )

            # 3. No threads found?
            if not (rows := await cur.fetchall()):
                return []

            # 4. Return the threads
            return [Thread.model_validate(row) for row in rows]

    async def list_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> list[Thread]:
        """List all threads for the given agent."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)

        async with self._cursor() as cur:
            # 2. Get the threads (and check if the user has access)
            await cur.execute(
                """SELECT t.*
                   FROM v2.thread t
                   WHERE t.agent_id = %(agent_id)s::uuid
                   AND v2.check_user_access(t.user_id, %(user_id)s::uuid)""",
                {"agent_id": agent_id, "user_id": user_id},
            )

            # 3. No threads found?
            if not (rows := await cur.fetchall()):
                return []

            # 4. Return the threads
            return [Thread.model_validate(row) for row in rows]

    async def get_thread(self, user_id: str, thread_id: str) -> Thread:
        """Get a thread by ID with its messages."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            # 2. Get the thread (and check if the user has access)
            await cur.execute(
                """SELECT
                    t.*,
                    v2.check_user_access(t.user_id, %(user_id)s::uuid) as has_access
                   FROM v2.thread t
                   WHERE t.thread_id = %(thread_id)s::uuid""",
                {"thread_id": thread_id, "user_id": user_id},
            )

            # 3. No thread found?
            if not (thread_row := await cur.fetchone()):
                raise ThreadNotFoundError(f"Thread {thread_id} not found")

            # 4. Check if the user has access
            if not thread_row.pop("has_access"):
                raise UserAccessDeniedError(f"Access denied to thread {thread_id}")

            # 5. Then get all messages for this thread
            messages = await self.get_thread_messages(thread_id)

            # 6. Create thread with messages
            thread_dict = thread_row | {"messages": messages or []}
            return Thread.model_validate(thread_dict)

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        """Update a thread."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)

        async with self._cursor() as cur:
            # 2. Check if the user has access
            await cur.execute(
                """SELECT v2.check_user_access(
                     t.user_id, %(user_id)s::uuid
                   ) as has_access
                   FROM v2.thread t
                   WHERE t.thread_id = %(thread_id)s::uuid""",
                {"thread_id": thread.thread_id, "user_id": user_id},
            )

            # 3. If the thread was found, we must have access
            if access_row := await cur.fetchone():
                if not access_row.pop("has_access"):
                    raise UserAccessDeniedError(
                        f"Access denied to thread {thread.thread_id}",
                    )

            # 4. Prepare the thread for upsert
            thread_dict = thread.model_dump() | {"user_id": user_id}
            thread_dict["metadata"] = Jsonb(thread_dict["metadata"])
            messages = [
                ThreadMessage.model_validate(m) for m in thread_dict.pop("messages", [])
            ]

            # 5. Upsert the thread
            try:
                await cur.execute(
                    """INSERT INTO v2.thread
                    (thread_id, name, user_id, agent_id,
                    created_at, updated_at, metadata)
                    VALUES (%(thread_id)s::uuid, %(name)s, %(user_id)s::uuid,
                            %(agent_id)s::uuid, %(created_at)s, %(updated_at)s,
                            %(metadata)s)
                    ON CONFLICT (thread_id)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        user_id = EXCLUDED.user_id,
                        agent_id = EXCLUDED.agent_id,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    WHERE v2.check_user_access(v2.thread.user_id, %(user_id)s::uuid)""",
                    thread_dict,
                )
            except UniqueViolation as e:
                if "duplicate key value violates unique constraint" in str(e):
                    raise RecordAlreadyExistsError(
                        f"Thread {thread.thread_id} already exists",
                    ) from e
                raise e
            except ForeignKeyViolation as e:
                raise ReferenceIntegrityError(
                    "Invalid foreign key reference updating thread",
                ) from e
            except Exception:
                raise

            # 6. Overwrite messages
            await self.overwrite_thread_messages(
                thread.thread_id,
                messages,
                cursor=cur,
            )

    async def delete_thread(self, user_id: str, thread_id: str) -> None:
        """Delete a thread."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            # 2. First check if the thread exists and if user has access
            await cur.execute(
                """SELECT
                    t.*,
                    v2.check_user_access(t.user_id, %(user_id)s::uuid) as has_access
                   FROM v2.thread t
                   WHERE t.thread_id = %(thread_id)s::uuid""",
                {"thread_id": thread_id, "user_id": user_id},
            )

            # 3. Check if thread exists
            if not (thread_row := await cur.fetchone()):
                raise ThreadNotFoundError(f"Thread {thread_id} not found")

            # 4. Check if user has access
            if not thread_row.pop("has_access"):
                raise UserAccessDeniedError(f"Access denied to thread {thread_id}")

            # 5. Delete the thread
            await cur.execute(
                """DELETE FROM v2.thread t
                   WHERE t.thread_id = %(thread_id)s::uuid""",
                {"thread_id": thread_id},
            )

    async def count_threads(self) -> int:
        """Count the number of threads."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM v2.thread")
            if row := await cur.fetchone():
                return row["count"]
        return 0

    async def delete_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
        thread_ids: list[str] | None = None,
    ) -> None:
        """Delete all threads for a given agent and user, or delete only the
        specified thread_ids if provided."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)
        if thread_ids:
            for tid in thread_ids:
                self._validate_uuid(tid)

        async with self._cursor() as cur:
            if thread_ids:
                await cur.execute(
                    """
                    DELETE FROM v2.thread
                    WHERE agent_id = %(agent_id)s::uuid
                      AND v2.check_user_access(user_id, %(user_id)s::uuid)
                      AND thread_id = ANY(%(thread_ids)s::uuid[])
                    """,
                    {
                        "agent_id": agent_id,
                        "user_id": user_id,
                        "thread_ids": thread_ids,
                    },
                )
            else:
                await cur.execute(
                    """
                    DELETE FROM v2.thread
                    WHERE agent_id = %(agent_id)s::uuid
                      AND v2.check_user_access(user_id, %(user_id)s::uuid)
                    """,
                    {"agent_id": agent_id, "user_id": user_id},
                )
