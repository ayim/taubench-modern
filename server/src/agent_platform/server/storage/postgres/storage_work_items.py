import json
from collections.abc import Sequence

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    WorkItemNotFoundError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageWorkItemsMixin(CursorMixin, CommonMixin):
    """Mixin providing PostgreSQL-based work-item operations."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _convert_work_item_json_fields(self, item_dict: dict) -> dict:
        """Convert JSON string columns to Python objects if needed."""
        if "initial_messages" in item_dict and isinstance(item_dict["initial_messages"], str):
            item_dict["initial_messages"] = json.loads(item_dict["initial_messages"])
        if "messages" in item_dict and isinstance(item_dict["messages"], str):
            item_dict["messages"] = json.loads(item_dict["messages"])
        if "payload" in item_dict and isinstance(item_dict["payload"], str):
            item_dict["payload"] = json.loads(item_dict["payload"])
        if "callbacks" in item_dict and isinstance(item_dict["callbacks"], str):
            item_dict["callbacks"] = json.loads(item_dict["callbacks"])
        return item_dict

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def create_work_item(self, work_item: WorkItem) -> None:
        """Insert a new work-item record into the database."""

        # Validate UUIDs that should be valid
        self._validate_uuid(work_item.user_id)
        self._validate_uuid(work_item.created_by)
        if work_item.agent_id is not None:
            self._validate_uuid(work_item.agent_id)
        self._validate_uuid(work_item.work_item_id)
        if work_item.thread_id is not None:
            self._validate_uuid(work_item.thread_id)

        work_item_dict = work_item.model_dump()
        work_item_dict["initial_messages"] = Jsonb(work_item_dict["initial_messages"])
        work_item_dict["messages"] = Jsonb(work_item_dict["messages"])
        work_item_dict["payload"] = Jsonb(work_item_dict["payload"])
        work_item_dict["callbacks"] = Jsonb(work_item_dict["callbacks"])
        user, _ = await self.get_or_create_user(work_item.user_id)
        work_item_dict["user_subject"] = user.sub

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.work_items (
                        work_item_id, user_id, created_by, agent_id,
                        thread_id, status, created_at, updated_at, completed_by,
                        status_updated_at, status_updated_by,
                        messages, payload, callbacks, initial_messages, user_subject, work_item_name
                    ) VALUES (
                        %(work_item_id)s::uuid, %(user_id)s::uuid,
                        %(created_by)s::uuid, %(agent_id)s::uuid, %(thread_id)s::uuid,
                        %(status)s, %(created_at)s, %(updated_at)s, %(completed_by)s,
                        %(status_updated_at)s, %(status_updated_by)s,
                        %(messages)s, %(payload)s, %(callbacks)s, %(initial_messages)s,
                        %(user_subject)s, %(work_item_name)s
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
        agent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        created_by: str | None = None,
    ) -> list[WorkItem]:
        """List all work items. If *agent_id* is provided, the list is further filtered to that
        agent. If *created_by* is provided, the list is further filtered to work items created
        by that user."""

        if agent_id is not None:
            self._validate_uuid(agent_id)
        if created_by is not None:
            self._validate_uuid(created_by)

        # Use a sentinel UUID when *agent_id* or *created_by* is None so that we can keep a
        # single query without running into Postgres' "ambiguous parameter"
        # issue for untyped NULLs. The all-zero UUID will never match a real
        # agent_id or created_by (because agent_id and created_by are generated with uuid4()).
        sentinel_agent_uuid = "00000000-0000-0000-0000-000000000000"
        sentinel_created_by_uuid = "00000000-0000-0000-0000-000000000000"

        params: dict[str, object] = {
            # If agent_id is None we pass the sentinel value; the SQL logic
            # treats that the same as "no filtering".
            "agent_id": agent_id or sentinel_agent_uuid,
            # Extra flag so the OR condition knows whether to apply the filter.
            "agent_filter_on": agent_id is not None,
            # Limit to N rows
            "limit": limit,
            # ... starting from the Mth row
            "offset": offset,
            "created_by": created_by or sentinel_created_by_uuid,
            "created_by_filter_on": created_by is not None,
        }

        query = """
            SELECT w.*
              FROM v2.work_items w
             WHERE (%(agent_filter_on)s = FALSE OR w.agent_id = %(agent_id)s::uuid)
               AND (%(created_by_filter_on)s = FALSE OR w.created_by = %(created_by)s::uuid)
             ORDER BY w.created_at DESC
             LIMIT %(limit)s
            OFFSET %(offset)s
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
        status_updated_by: WorkItemStatusUpdatedBy = WorkItemStatusUpdatedBy.SYSTEM,
    ) -> None:
        """Update the *status* of a work-item."""

        self._validate_uuid(user_id)
        self._validate_uuid(work_item_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2.work_items
                   SET status = %(status)s,
                       status_updated_by = %(status_updated_by)s,
                       status_updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
                 WHERE work_item_id = %(work_item_id)s::uuid
                   AND v2.check_user_access(user_id, %(user_id)s::uuid)
                """,
                {
                    "status": status.value if isinstance(status, WorkItemStatus) else str(status),
                    "work_item_id": work_item_id,
                    "user_id": user_id,
                    "status_updated_by": status_updated_by.value,
                },
            )

    async def complete_work_item(
        self,
        user_id: str,
        work_item_id: str,
        completed_by: WorkItemCompletedBy,
    ) -> None:
        """Complete a work item with the specified completed_by value."""

        self._validate_uuid(user_id)
        self._validate_uuid(work_item_id)

        query = """
            UPDATE v2.work_items
               SET status = %(status)s,
                   completed_by = %(completed_by)s,
                   status_updated_by = %(status_updated_by)s,
                   status_updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                   updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
             WHERE work_item_id = %(work_item_id)s::uuid
               AND v2.check_user_access(user_id, %(user_id)s::uuid)
        """
        params = {
            "status": WorkItemStatus.COMPLETED.value,
            "work_item_id": work_item_id,
            "user_id": user_id,
            "completed_by": completed_by.value
            if isinstance(completed_by, WorkItemCompletedBy)
            else str(completed_by),
            "status_updated_by": completed_by.as_status_updated_by().value,
        }

        async with self._cursor() as cur:
            await cur.execute(query, params)

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

    async def update_work_item(self, work_item: WorkItem) -> None:
        """Update a work item."""
        self._validate_uuid(work_item.user_id)
        self._validate_uuid(work_item.work_item_id)

        # Convert work item to dict
        work_item_data = work_item.model_dump()

        work_item_data["initial_messages"] = (
            Jsonb([msg.model_dump() for msg in work_item.initial_messages])
            if work_item.initial_messages
            else Jsonb([])
        )

        # Convert messages, payload, and callbacks to Jsonb
        work_item_data["messages"] = (
            Jsonb([msg.model_dump() for msg in work_item.messages])
            if work_item.messages
            else Jsonb([])
        )
        work_item_data["payload"] = Jsonb(work_item.payload)
        work_item_data["callbacks"] = (
            Jsonb([callback.model_dump() for callback in work_item.callbacks])
            if work_item.callbacks
            else Jsonb([])
        )

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2.work_items
                   SET agent_id = %(agent_id)s,
                       thread_id = %(thread_id)s,
                       initial_messages = %(initial_messages)s,
                       messages = %(messages)s,
                       payload = %(payload)s,
                       callbacks = %(callbacks)s,
                       status = %(status)s,
                       completed_by = %(completed_by)s,
                       status_updated_at = %(status_updated_at)s,
                       status_updated_by = %(status_updated_by)s,
                       updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                       work_item_name = %(work_item_name)s
                 WHERE work_item_id = %(work_item_id)s::uuid
                   AND v2.check_user_access(user_id, %(user_id)s::uuid)
                """,
                work_item_data,
            )
