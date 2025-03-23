import json

from aiosqlite import Cursor, IntegrityError
from structlog import get_logger

from agent_server_types_v2.thread import ThreadMessage
from sema4ai_agent_server.storage.v2.errors_v2 import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ThreadNotFoundError,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.common import CommonMixin


class SQLiteStorageMessagesMixin(CommonMixin):
    """
    Mixin providing SQLite-based message operations.
    """

    _logger = get_logger(__name__)

    async def overwrite_thread_messages_v2(
        self,
        thread_id: str,
        messages: list[ThreadMessage],
        cursor: Cursor | None = None,
    ) -> None:
        """
        Overwrite the messages for the given thread:
          1) Delete existing messages
          2) Batch insert the new ones
        """
        self._validate_uuid(thread_id)

        try:
            async with self._cursor(cursor) as cur:
                # 1) Delete existing messages
                await cur.execute(
                    "DELETE FROM v2_thread_message WHERE thread_id = :thread_id",
                    {"thread_id": thread_id},
                )

                # 2) If no new messages, we're done
                if not messages:
                    return

                # 3) Insert new messages in order
                inserts = []
                for i, msg in enumerate(messages):
                    inserts.append({
                        "message_id": msg["message_id"],
                        "thread_id": thread_id,
                        "sequence_number": i,
                        "role": msg["role"],
                        "content": json.dumps(msg["content"]),
                        "agent_metadata": json.dumps(msg["agent_metadata"]),
                        "server_metadata": json.dumps(msg["server_metadata"]),
                        "created_at": msg["created_at"],
                        "updated_at": msg["updated_at"],
                    })

                await cur.executemany(
                    """
                    INSERT INTO v2_thread_message (
                        message_id, thread_id, sequence_number, role, content,
                        agent_metadata, server_metadata, created_at, updated_at
                    ) VALUES (
                        :message_id, :thread_id, :sequence_number, :role, :content,
                        :agent_metadata, :server_metadata, :created_at, :updated_at
                    )
                    """,
                    inserts,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_thread_message.message_id" in str(e):
                message_ids = ','.join([msg.message_id for msg in messages])
                raise RecordAlreadyExistsError(
                    f"One of the following messages already exists: {message_ids}",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating message",
            ) from e

    async def add_message_to_thread_v2(
        self,
        user_id: str,
        thread_id: str,
        message: ThreadMessage,
    ) -> None:
        """Add a message to a thread, ensuring the thread exists
        and the user can access it."""
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        # Check existence and access at the thread level if desired
        if not await self._thread_exists(thread_id):
            raise ThreadNotFoundError(f"Thread {thread_id} not found")

        try:
            async with self._cursor() as cur:
                # Get the last sequence number
                await cur.execute(
                    """
                    SELECT COALESCE(MAX(sequence_number), -1) AS max_seq
                    FROM v2_thread_message
                    WHERE thread_id = :thread_id
                    """,
                    {"thread_id": thread_id},
                )
                row = await cur.fetchone()
                next_sequence = (row["max_seq"] + 1) if row else 0

                message_dict = message.to_json_dict()

                # Insert the new message
                await cur.execute(
                    """
                    INSERT INTO v2_thread_message (
                        message_id, thread_id, sequence_number, role, content,
                        agent_metadata, server_metadata, created_at, updated_at,
                        parent_run_id
                    ) VALUES (
                        :message_id, :thread_id, :sequence_number, :role, :content,
                        :agent_metadata, :server_metadata, :created_at, :updated_at,
                        :parent_run_id
                    )
                    """,
                    {
                        "message_id": message_dict["message_id"],
                        "thread_id": thread_id,
                        "sequence_number": next_sequence,
                        "role": message_dict["role"],
                        "content": json.dumps(message_dict["content"]),
                        "agent_metadata": json.dumps(message_dict["agent_metadata"]),
                        "server_metadata": json.dumps(message_dict["server_metadata"]),
                        "created_at": message_dict["created_at"],
                        "updated_at": message_dict["updated_at"],
                        "parent_run_id": message_dict["parent_run_id"],
                    },
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_thread_message.message_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Message {message_dict['message_id']} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating message",
            ) from e

    async def get_thread_messages_v2(self, thread_id: str) -> list[ThreadMessage]:
        """Get messages for the given thread,
        in ascending sequence/creation order."""
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    message_id, created_at, updated_at,
                    role, content, agent_metadata, server_metadata
                FROM v2_thread_message
                WHERE thread_id = :thread_id
                ORDER BY sequence_number, created_at, message_id
                """,
                {"thread_id": thread_id},
            )
            rows = await cur.fetchall()

        if not rows:
            return []

        messages = []
        for row in rows:
            row_dict = dict(row)
            row_dict["content"] = (
                json.loads(row_dict["content"])
                if row_dict["content"] else []
            )
            row_dict["agent_metadata"] = (
                json.loads(row_dict["agent_metadata"])
                if row_dict["agent_metadata"]
                else {}
            )
            row_dict["server_metadata"] = (
                json.loads(row_dict["server_metadata"])
                if row_dict["server_metadata"] else {}
            )
            messages.append(ThreadMessage.from_dict(row_dict))

        return messages

    async def get_messages_by_parent_run_id_v2(
        self,
        user_id: str,
        parent_run_id: str,
    ) -> list[ThreadMessage]:
        """Get messages for the given parent run ID,
        in ascending sequence/creation order."""
        self._validate_uuid(user_id)
        self._validate_uuid(parent_run_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    message_id, created_at, updated_at,
                    role, content, agent_metadata, server_metadata,
                    parent_run_id
                FROM v2_thread_message
                WHERE parent_run_id = :parent_run_id
                AND v2_check_user_access(
                    t.user_id, :user_id
                )
                ORDER BY sequence_number, created_at, message_id
                """,
                {"parent_run_id": parent_run_id, "user_id": user_id},
            )
            rows = await cur.fetchall()

        if not rows:
            return []

        messages = []
        for row in rows:
            row_dict = dict(row)
            row_dict["content"] = (
                json.loads(row_dict["content"])
                if row_dict["content"] else []
            )
            row_dict["agent_metadata"] = (
                json.loads(row_dict["agent_metadata"])
                if row_dict["agent_metadata"]
                else {}
            )
            row_dict["server_metadata"] = (
                json.loads(row_dict["server_metadata"])
                if row_dict["server_metadata"] else {}
            )
            messages.append(ThreadMessage.from_dict(row_dict))

        return messages

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    async def _thread_exists(self, user_id: str, thread_id: str) -> bool:
        """Helper to check if a thread with the given ID actually
        exists and the user has access to it."""
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT 1 FROM v2_thread
                WHERE thread_id = :thread_id
                AND v2_check_user_access(
                    t.user_id, :user_id
                )
                LIMIT 1
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
