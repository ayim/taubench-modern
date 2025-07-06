import json
from collections.abc import Sequence

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    WorkItemNotFoundError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageWorkItemsMixin(CommonMixin):
    """Mixin providing PostgreSQL-based work-item operations."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _convert_work_item_json_fields(self, item_dict: dict) -> dict:
        """Convert JSON string columns to Python objects if needed."""
        if "messages" in item_dict and isinstance(item_dict["messages"], str):
            item_dict["messages"] = json.loads(item_dict["messages"])
        if "payload" in item_dict and isinstance(item_dict["payload"], str):
            item_dict["payload"] = json.loads(item_dict["payload"])
        return item_dict

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def create_work_item(self, work_item: WorkItem) -> None:
        """Insert a new work-item record into the database."""

        # Validate UUIDs that should be valid
        self._validate_uuid(work_item.user_id)
        self._validate_uuid(work_item.agent_id)
        self._validate_uuid(work_item.work_item_id)
        if work_item.thread_id is not None:
            self._validate_uuid(work_item.thread_id)

        work_item_dict = work_item.model_dump()
        work_item_dict["messages"] = Jsonb(work_item_dict["messages"])
        work_item_dict["payload"] = Jsonb(work_item_dict["payload"])

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.work_items (
                        work_item_id, user_id, agent_id, thread_id, status,
                        created_at, updated_at, completed_by,
                        status_updated_at, status_updated_by,
                        messages, payload
                    ) VALUES (
                        %(work_item_id)s::uuid, %(user_id)s::uuid,
                        %(agent_id)s::uuid, %(thread_id)s::uuid, %(status)s,
                        %(created_at)s, %(updated_at)s, %(completed_by)s,
                        %(status_updated_at)s, %(status_updated_by)s,
                        %(messages)s, %(payload)s
                    )
                    """,
                    work_item_dict,
                )
        except UniqueViolation as exc:
            if "duplicate key value" in str(exc):
                raise RecordAlreadyExistsError(
                    f"Work item {work_item.work_item_id} already exists",
                ) from exc
            raise
        except ForeignKeyViolation as exc:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference inserting work item",
            ) from exc

    async def get_work_item(self, work_item_id: str) -> WorkItem:
        """Retrieve a work-item by its ID."""
        self._validate_uuid(work_item_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM v2.work_items WHERE work_item_id = %(id)s::uuid
                """,
                {"id": work_item_id},
            )
            row = await cur.fetchone()

        if row is None:
            raise WorkItemNotFoundError(work_item_id)

        return WorkItem.model_validate(self._convert_work_item_json_fields(dict(row)))

    async def get_work_items_by_ids(self, work_item_ids: list[str]) -> list[WorkItem]:
        """Retrieve multiple work-items given their IDs."""
        if not work_item_ids:
            return []

        for wid in work_item_ids:
            self._validate_uuid(wid)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM v2.work_items WHERE work_item_id = ANY(%(ids)s::uuid[])
                """,
                {"ids": work_item_ids},
            )
            rows = await cur.fetchall()

        return [
            WorkItem.model_validate(self._convert_work_item_json_fields(dict(row))) for row in rows
        ]

    async def list_work_items(
        self,
        user_id: str,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkItem]:
        """List work-items accessible to *user_id* (optionally filtered by agent)."""
        self._validate_uuid(user_id)
        if agent_id is not None:
            self._validate_uuid(agent_id)

        # Use a sentinel UUID when *agent_id* is None so that we can keep a
        # single query without running into Postgres' "ambiguous parameter"
        # issue for untyped NULLs. The all-zero UUID will never match a real
        # agent_id (because agent_id is generated with uuid4()).
        sentinel_agent_uuid = "00000000-0000-0000-0000-000000000000"

        params: dict[str, object] = {
            "user_id": user_id,
            # If agent_id is None we pass the sentinel value; the SQL logic
            # treats that the same as "no filtering".
            "agent_id": agent_id or sentinel_agent_uuid,
            # Extra flag so the OR condition knows whether to apply the filter.
            "agent_filter_on": agent_id is not None,
            "limit": limit,
        }

        query = """
            SELECT w.*
              FROM v2.work_items w
             WHERE v2.check_user_access(w.user_id, %(user_id)s::uuid)
               AND (%(agent_filter_on)s = FALSE OR w.agent_id = %(agent_id)s::uuid)
             ORDER BY w.created_at
             LIMIT %(limit)s
        """

        async with self._cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        return [
            WorkItem.model_validate(self._convert_work_item_json_fields(dict(row))) for row in rows
        ]

    async def update_work_item_status(
        self,
        user_id: str,
        work_item_id: str,
        status: WorkItemStatus,
    ) -> None:
        """Update the *status* of a work-item."""

        self._validate_uuid(user_id)
        self._validate_uuid(work_item_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2.work_items
                   SET status = %(status)s,
                       status_updated_by = %(user_id)s,
                       status_updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                 WHERE work_item_id = %(work_item_id)s::uuid
                   AND v2.check_user_access(user_id, %(user_id)s::uuid)
                """,
                {
                    "status": status.value if isinstance(status, WorkItemStatus) else str(status),
                    "work_item_id": work_item_id,
                    "user_id": user_id,
                },
            )

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------
    async def get_pending_work_item_ids(self, limit: int = 10) -> list[str]:
        """Atomically claim a batch of PENDING work-items and mark them EXECUTING."""

        async with self._cursor() as cur:
            await cur.execute(
                """
                WITH candidate AS (
                    SELECT work_item_id
                      FROM v2.work_items
                     WHERE status = %(pending)s
                  ORDER BY created_at
                     LIMIT %(limit)s
                     FOR UPDATE SKIP LOCKED
                )
                UPDATE v2.work_items AS w
                   SET status = %(executing)s,
                       status_updated_by = 'SYSTEM',
                       status_updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                  FROM candidate
                 WHERE w.work_item_id = candidate.work_item_id
                RETURNING w.work_item_id
                """,
                {
                    "pending": WorkItemStatus.PENDING.value,
                    "executing": WorkItemStatus.EXECUTING.value,
                    "limit": limit,
                },
            )
            rows = await cur.fetchall()

        # Ensure we return plain strings for consistency with the rest of the
        # storage interface (SQLite implementation already does this).
        # Psycopg returns UUID instances by default, so we cast them to str.
        return [str(row["work_item_id"]) for row in rows]

    async def mark_incomplete_work_items_as_error(self, work_item_ids: Sequence[str]) -> None:
        """Mark provided work-items as ERROR if they are still PENDING/EXECUTING."""
        if not work_item_ids:
            return

        for wid in work_item_ids:
            self._validate_uuid(wid)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2.work_items
                   SET status = %(error)s,
                       status_updated_by = 'SYSTEM',
                       status_updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                 WHERE work_item_id = ANY(%(ids)s::uuid[])
                   AND status IN ('PENDING', 'EXECUTING')
                """,
                {"ids": work_item_ids, "error": WorkItemStatus.ERROR.value},
            )

    async def update_work_item_from_thread(
        self,
        user_id: str,
        work_item_id: str,
        thread_id: str,
    ) -> None:
        """Update a work item from a thread."""
        self._validate_uuid(user_id)
        self._validate_uuid(work_item_id)
        self._validate_uuid(thread_id)

        thread_messages = await self.get_thread_messages(thread_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2.work_items
                   SET thread_id = %(thread_id)s,
                       messages = %(messages)s,
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                 WHERE work_item_id = %(work_item_id)s::uuid
                   AND v2.check_user_access(user_id, %(user_id)s::uuid)
                """,
                {
                    "thread_id": thread_id,
                    "work_item_id": work_item_id,
                    "user_id": user_id,
                    "messages": Jsonb([msg.model_dump() for msg in thread_messages]),
                },
            )
