import json

from aiosqlite import IntegrityError
from structlog import get_logger

from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ThreadNotFoundError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.sqlite.storage_messages import (
    SQLiteStorageMessagesMixin,
)


class SQLiteStorageThreadsMixin(SQLiteStorageMessagesMixin):
    """
    Mixin providing SQLite-based thread operations.
    """

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Threads
    # -------------------------------------------------------------------------
    async def list_threads(
        self,
        user_id: str,
        include_trial_threads: bool = False,
    ) -> list[Thread]:
        """List all threads for a given user."""
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    t.thread_id,
                    t.agent_id,
                    t.user_id,
                    t.name,
                    t.created_at,
                    t.updated_at,
                    t.trial_id,
                    t.metadata,
                    t.work_item_id,
                    t.parent_trace_id,
                    t.parent_span_id
                FROM v2_thread t
                WHERE v2_check_user_access(t.user_id, :user_id) = 1
                  AND (:include_trial_threads = 1 OR t.trial_id IS NULL)
                ORDER BY t.created_at DESC
                """,
                {
                    "user_id": user_id,
                    "include_trial_threads": int(include_trial_threads),
                },
            )
            rows = await cur.fetchall()

        if not rows:
            return []
        return [Thread.model_validate(self._convert_thread_json_fields(dict(r))) for r in rows]

    async def list_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
        include_trial_threads: bool = False,
    ) -> list[Thread]:
        """List all threads for a specific agent if user has access."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    t.thread_id,
                    t.agent_id,
                    t.user_id,
                    t.name,
                    t.created_at,
                    t.updated_at,
                    t.trial_id,
                    t.metadata,
                    t.work_item_id,
                    t.parent_trace_id,
                    t.parent_span_id
                FROM v2_thread t
                WHERE t.agent_id = :agent_id
                  AND v2_check_user_access(t.user_id, :user_id) = 1
                  AND (:include_trial_threads = 1 OR t.trial_id IS NULL)
                ORDER BY t.created_at DESC
                """,
                {
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "include_trial_threads": int(include_trial_threads),
                },
            )
            rows = await cur.fetchall()

        if not rows:
            return []
        return [Thread.model_validate(self._convert_thread_json_fields(dict(r))) for r in rows]

    async def get_thread(self, user_id: str, thread_id: str) -> Thread:
        """
        Get a thread by ID (with user access check), then load messages.
        Raise ThreadNotFoundError if not found.
        Raise UserAccessDeniedError if user lacks access.
        """
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        # Get the thread row
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    t.thread_id,
                    t.agent_id,
                    t.user_id,
                    t.name,
                    t.created_at,
                    t.updated_at,
                    t.metadata,
                    t.trial_id,
                    t.work_item_id,
                    t.parent_trace_id,
                    t.parent_span_id,
                    v2_check_user_access(t.user_id, :user_id) AS has_access
                FROM v2_thread t
                WHERE t.thread_id = :thread_id
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
            row = await cur.fetchone()

        if not row:
            # No thread row at all => not found
            raise ThreadNotFoundError(f"Thread {thread_id} not found")

        if not row["has_access"]:
            raise UserAccessDeniedError(f"Access denied to thread {thread_id}")

        # Load messages
        thread_dict = dict(row)
        thread_dict.pop("has_access", None)
        messages = await self.get_thread_messages(thread_id)
        thread_dict["messages"] = messages
        return Thread.model_validate(self._convert_thread_json_fields(thread_dict))

    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        """Upsert a thread record, then overwrite its messages."""
        self._validate_uuid(user_id)
        self._validate_uuid(thread.thread_id)

        # Convert to JSON for DB
        thread_dict = thread.model_dump()
        messages = [ThreadMessage.model_validate(m) for m in thread_dict.pop("messages", [])]
        thread_dict["metadata"] = json.dumps(thread_dict["metadata"])

        try:
            async with self._transaction() as cur:
                # Insert or update the thread
                # Use a separate parameter for the requesting user so access checks are correct
                params = thread_dict | {"requester_user_id": user_id}
                await cur.execute(
                    """
                    INSERT INTO v2_thread (
                        thread_id, name, user_id, agent_id,
                        created_at, updated_at, metadata, work_item_id, trial_id,
                        parent_trace_id, parent_span_id
                    )
                    VALUES (
                        :thread_id, :name, :user_id, :agent_id,
                        :created_at, :updated_at, :metadata, :work_item_id, :trial_id,
                        :parent_trace_id, :parent_span_id
                    )
                    ON CONFLICT(thread_id) DO UPDATE SET
                        name = excluded.name,
                        agent_id = excluded.agent_id,
                        updated_at = excluded.updated_at,
                        metadata = excluded.metadata,
                        work_item_id = excluded.work_item_id,
                        trial_id = excluded.trial_id,
                        parent_trace_id = COALESCE(v2_thread.parent_trace_id, excluded.parent_trace_id),
                        parent_span_id = COALESCE(v2_thread.parent_span_id, excluded.parent_span_id)
                    WHERE v2_check_user_access(v2_thread.user_id, :requester_user_id) = 1
                    RETURNING thread_id
                    """,
                    params,
                )

                row = await cur.fetchone()
                if not row:
                    # No row returned from RETURNING indicates access denied
                    raise UserAccessDeniedError(
                        f"Access denied to thread {thread.thread_id}",
                    )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_thread.thread_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Thread {thread.thread_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating thread",
            ) from e

        # Overwrite messages
        await self.overwrite_thread_messages(thread.thread_id, messages)

    async def delete_thread(self, user_id: str, thread_id: str) -> None:
        """Delete a thread, raising if not found or no access."""
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        async with self._transaction() as cur:
            await cur.execute(
                """
                SELECT v2_check_user_access(t.user_id, :user_id) AS has_access
                FROM v2_thread t
                WHERE t.thread_id = :thread_id
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
            row = await cur.fetchone()
            if not row:
                raise ThreadNotFoundError(f"Thread {thread_id} not found")
            if not row["has_access"]:
                raise UserAccessDeniedError(f"Access denied to thread {thread_id}")

        async with self._transaction() as cur:
            await cur.execute(
                """
                DELETE FROM v2_thread
                WHERE thread_id = :thread_id
                """,
                {"thread_id": thread_id},
            )

    async def set_thread_trace_context(
        self,
        user_id: str,
        thread_id: str,
        parent_trace_id: str,
        parent_span_id: str,
    ) -> None:
        """Set trace context fields for a thread."""
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        async with self._transaction() as cur:
            await cur.execute(
                """
                UPDATE v2_thread
                SET parent_trace_id = :parent_trace_id,
                    parent_span_id = :parent_span_id
                WHERE thread_id = :thread_id
                  AND v2_check_user_access(user_id, :user_id) = 1
                """,
                {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "parent_trace_id": parent_trace_id,
                    "parent_span_id": parent_span_id,
                },
            )

    async def count_threads(self) -> int:
        """Count the number of threads (no user-based filter)."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2_thread")
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_threads_for_agent(self, agent_id: str) -> int:
        """Count the number of threads for a given agent (no user-based filter)."""
        async with self._cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM v2_thread WHERE agent_id = :agent_id", {"agent_id": agent_id}
            )
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_messages(self) -> int:
        """Count the number of messages."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2_thread_message")
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def delete_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
        thread_ids: list[str] | None = None,
    ) -> None:
        """Delete all threads for a given agent and user, or delete only the
        specified thread_ids if provided."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)
        if thread_ids:
            for tid in thread_ids:
                self._validate_uuid(tid)
        async with self._transaction() as cur:
            if thread_ids:
                await cur.execute(
                    """
                    DELETE FROM v2_thread
                    WHERE agent_id = :agent_id
                      AND v2_check_user_access(user_id, :user_id) = 1
                      AND thread_id IN ({})
                    """.format(",".join([":tid" + str(i) for i in range(len(thread_ids))])),
                    {
                        "agent_id": agent_id,
                        "user_id": user_id,
                        **{f"tid{i}": tid for i, tid in enumerate(thread_ids)},
                    },
                )
            else:
                await cur.execute(
                    """
                    DELETE FROM v2_thread
                    WHERE agent_id = :agent_id
                      AND v2_check_user_access(user_id, :user_id) = 1
                    """,
                    {"agent_id": agent_id, "user_id": user_id},
                )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _convert_thread_json_fields(self, thread_dict: dict) -> dict:
        """Convert JSON string fields in thread dict to Python objects."""
        for field in ["metadata"]:
            if thread_dict.get(field) is not None:
                thread_dict[field] = json.loads(thread_dict[field])
            else:
                thread_dict[field] = {}
        return thread_dict
