import json

from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage.errors import WorkItemNotFoundError
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageWorkItemsMixin(CommonMixin):
    """Mixin providing SQLite-based work-item operations."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _convert_work_item_json_fields(self, item_dict: dict) -> dict:
        """Convert JSON string fields to their Python counterparts."""
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
        """Insert a new work item record."""
        # Validate IDs that should be UUIDs
        self._validate_uuid(work_item.user_id)
        if work_item.agent_id is not None:
            self._validate_uuid(work_item.agent_id)
        self._validate_uuid(work_item.work_item_id)
        if work_item.thread_id is not None:
            self._validate_uuid(work_item.thread_id)

        work_item_dict = work_item.model_dump()
        work_item_dict["messages"] = json.dumps(work_item_dict["messages"])
        work_item_dict["payload"] = json.dumps(work_item_dict["payload"])
        work_item_dict["callbacks"] = json.dumps(work_item_dict["callbacks"])

        async with self._cursor() as cur:
            await cur.execute(
                """
                INSERT INTO v2_work_items (
                    work_item_id, user_id, agent_id, thread_id, status,
                    created_at, updated_at, completed_by,
                    status_updated_at, status_updated_by,
                    messages, payload, callbacks
                ) VALUES (
                    :work_item_id, :user_id, :agent_id, :thread_id, :status,
                    :created_at, :updated_at, :completed_by,
                    :status_updated_at, :status_updated_by,
                    :messages, :payload, :callbacks
                )
                """,
                work_item_dict,
            )

    async def get_work_item(self, work_item_id: str) -> WorkItem:
        """Retrieve a single work item by its ID."""
        self._validate_uuid(work_item_id)

        async with self._cursor() as cur:
            await cur.execute(
                "SELECT * FROM v2_work_items WHERE work_item_id = :id",
                {"id": work_item_id},
            )
            row = await cur.fetchone()

        if not row:
            raise WorkItemNotFoundError(work_item_id)

        return WorkItem.model_validate(self._convert_work_item_json_fields(dict(row)))

    async def get_work_items_by_ids(self, work_item_ids: list[str]) -> list[WorkItem]:
        """Retrieve multiple work items given a collection of IDs."""
        if not work_item_ids:
            return []

        for wid in work_item_ids:
            self._validate_uuid(wid)

        placeholders = ", ".join(f":id{i}" for i in range(len(work_item_ids)))
        params = {f"id{i}": wid for i, wid in enumerate(work_item_ids)}

        async with self._cursor() as cur:
            await cur.execute(
                f"SELECT * FROM v2_work_items WHERE work_item_id IN ({placeholders})",
                params,
            )
            rows = await cur.fetchall()

        return [WorkItem.model_validate(self._convert_work_item_json_fields(dict(r))) for r in rows]

    async def list_work_items(
        self,
        user_id: str,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkItem]:
        """List all work items accessible to *user_id*. If *agent_id* is
        provided, the list is further filtered to that agent."""

        self._validate_uuid(user_id)
        if agent_id is not None:
            self._validate_uuid(agent_id)

        params: dict[str, str | None] = {
            "user_id": user_id,
            "agent_id": agent_id,
            "limit": str(limit),
        }

        query = """
            SELECT w.*
              FROM v2_work_items w
             WHERE v2_check_user_access(w.user_id, :user_id) = 1
               AND (:agent_id IS NULL OR w.agent_id = :agent_id)
             ORDER BY w.created_at
             LIMIT :limit
        """

        async with self._cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        return [WorkItem.model_validate(self._convert_work_item_json_fields(dict(r))) for r in rows]

    async def update_work_item_status(
        self,
        user_id: str,
        work_item_id: str,
        status: WorkItemStatus,
    ) -> None:
        """Update the status of a single work item."""

        self._validate_uuid(user_id)
        self._validate_uuid(work_item_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2_work_items
                   SET status = :status,
                       status_updated_by = :user_id,
                       status_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                 WHERE work_item_id = :work_item_id
                   AND v2_check_user_access(user_id, :user_id) = 1
                """,
                {
                    "status": status.value if isinstance(status, WorkItemStatus) else str(status),
                    "work_item_id": work_item_id,
                    "user_id": user_id,
                },
            )

    # ------------------------------------------------------------------
    # Batch / workflow helpers
    # ------------------------------------------------------------------
    async def get_pending_work_item_ids(self, limit: int = 10) -> list[str]:
        """Atomically move the next PENDING work-items to EXECUTING and return their IDs."""

        async with self._cursor() as cur:
            # 1. Select candidate IDs in a CTE ordered by created_at, limited by *limit*
            # 2. Update their status to EXECUTING and return the IDs in one statement
            await cur.execute(
                """
                WITH candidate AS (
                    SELECT work_item_id
                      FROM v2_work_items
                     WHERE status = :pending
                  ORDER BY created_at
                     LIMIT :limit
                )
                UPDATE v2_work_items
                   SET status = :executing,
                       status_updated_by = 'SYSTEM',
                       status_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                 WHERE work_item_id IN (SELECT work_item_id FROM candidate)
                       AND status = :pending  -- prevents double claim
                RETURNING work_item_id
                """,
                {
                    "pending": WorkItemStatus.PENDING.value,
                    "executing": WorkItemStatus.EXECUTING.value,
                    "limit": limit,
                },
            )
            rows = await cur.fetchall()

        return [row["work_item_id"] for row in rows]

    async def mark_incomplete_work_items_as_error(self, work_item_ids: list[str]) -> None:
        """Mark given work items as ERROR if they are still PENDING/EXECUTING."""

        if not work_item_ids:
            return

        for wid in work_item_ids:
            self._validate_uuid(wid)

        placeholders = ", ".join(f":id{i}" for i in range(len(work_item_ids)))
        params = {f"id{i}": wid for i, wid in enumerate(work_item_ids)}
        params["error"] = WorkItemStatus.ERROR.value

        async with self._cursor() as cur:
            await cur.execute(
                f"""
                UPDATE v2_work_items
                   SET status = :error,
                       status_updated_by = 'SYSTEM',
                       status_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                 WHERE work_item_id IN ({placeholders})
                   AND status IN ('PENDING', 'EXECUTING')
                """,
                params,
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
                UPDATE v2_work_items
                   SET thread_id = :thread_id,
                       messages = :messages,
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                 WHERE work_item_id = :work_item_id
                   AND v2_check_user_access(user_id, :user_id) = 1
                """,
                {
                    "thread_id": thread_id,
                    "work_item_id": work_item_id,
                    "user_id": user_id,
                    "messages": json.dumps([msg.model_dump() for msg in thread_messages]),
                },
            )

    async def update_work_item(self, work_item: WorkItem) -> None:
        """Update a work item."""
        self._validate_uuid(work_item.user_id)
        self._validate_uuid(work_item.work_item_id)

        # Convert messages and payload to JSON strings
        messages_json = (
            json.dumps([msg.model_dump() for msg in work_item.messages])
            if work_item.messages
            else "[]"
        )
        payload_json = json.dumps(work_item.payload)

        async with self._cursor() as cur:
            await cur.execute(
                """
                UPDATE v2_work_items
                   SET agent_id = :agent_id,
                       thread_id = :thread_id,
                       messages = :messages,
                       payload = :payload,
                       status = :status,
                       completed_by = :completed_by,
                       status_updated_at = :status_updated_at,
                       status_updated_by = :status_updated_by,
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                 WHERE work_item_id = :work_item_id
                   AND v2_check_user_access(user_id, :user_id) = 1
                """,
                {
                    "agent_id": work_item.agent_id,
                    "thread_id": work_item.thread_id,
                    "messages": messages_json,
                    "payload": payload_json,
                    "status": work_item.status.value
                    if isinstance(work_item.status, WorkItemStatus)
                    else str(work_item.status),
                    "completed_by": work_item.completed_by,
                    "status_updated_at": work_item.status_updated_at,
                    "status_updated_by": work_item.status_updated_by,
                    "work_item_id": work_item.work_item_id,
                    "user_id": work_item.user_id,
                },
            )
