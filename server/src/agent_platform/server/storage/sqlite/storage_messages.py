import json

from aiosqlite import Cursor, IntegrityError
from structlog import get_logger

from agent_platform.core.thread import ThreadMessage
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ThreadNotFoundError,
    UserPermissionError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageMessagesMixin(CommonMixin):
    """
    Mixin providing SQLite-based message operations.
    """

    _logger = get_logger(__name__)

    async def overwrite_thread_messages(
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
                    inserts.append(
                        {
                            "message_id": msg.message_id,
                            "thread_id": thread_id,
                            "sequence_number": i,
                            "role": msg.role,
                            "content": json.dumps(
                                [c.model_dump() for c in msg.content],
                            ),
                            "agent_metadata": json.dumps(msg.agent_metadata),
                            "server_metadata": json.dumps(msg.server_metadata),
                            "created_at": msg.created_at,
                            "updated_at": msg.updated_at,
                            "parent_run_id": msg.parent_run_id,
                        },
                    )

                await cur.executemany(
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
                    inserts,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_thread_message.message_id" in str(e):
                message_ids = ",".join([msg.message_id for msg in messages])
                raise RecordAlreadyExistsError(
                    f"One of the following messages already exists: {message_ids}",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating message",
            ) from e

    async def add_message_to_thread(
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
        if not await self._thread_exists(user_id, thread_id):
            raise ThreadNotFoundError(f"Thread {thread_id} not found")

        try:
            async with self._cursor() as cur:
                message_dict = message.model_dump()

                # Check if message already exists
                await cur.execute(
                    """
                    SELECT sequence_number FROM v2_thread_message
                    WHERE message_id = :message_id
                    """,
                    {"message_id": message_dict["message_id"]},
                )
                existing_row = await cur.fetchone()

                if existing_row:
                    # Message exists, update it (preserving sequence number)
                    await cur.execute(
                        """
                        UPDATE v2_thread_message
                        SET role = :role,
                            content = :content,
                            agent_metadata = :agent_metadata,
                            server_metadata = :server_metadata,
                            updated_at = :updated_at
                        WHERE message_id = :message_id
                        """,
                        {
                            "message_id": message_dict["message_id"],
                            "role": message_dict["role"],
                            "content": json.dumps(message_dict["content"]),
                            "agent_metadata": json.dumps(message_dict["agent_metadata"]),
                            "server_metadata": json.dumps(message_dict["server_metadata"]),
                            "updated_at": message_dict["updated_at"],
                        },
                    )
                else:
                    # Message doesn't exist, get the next sequence number and insert
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
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating message",
            ) from e

    async def get_thread_messages(self, thread_id: str) -> list[ThreadMessage]:
        """Get messages for the given thread,
        in ascending sequence/creation order."""
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    message_id, created_at, updated_at,
                    role, content, agent_metadata, server_metadata,
                    parent_run_id
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
            row_dict["content"] = json.loads(row_dict["content"]) if row_dict["content"] else []
            row_dict["agent_metadata"] = (
                json.loads(row_dict["agent_metadata"]) if row_dict["agent_metadata"] else {}
            )
            row_dict["server_metadata"] = (
                json.loads(row_dict["server_metadata"]) if row_dict["server_metadata"] else {}
            )
            # Set commited=True and completed=True for messages retrieved from database
            row_dict["commited"] = True  # Note: using "commited" to match the field name
            row_dict["complete"] = True
            messages.append(ThreadMessage.model_validate(row_dict))

        return messages

    async def trim_messages_from_sequence(
        self,
        user_id: str,
        thread_id: str,
        message_id: str,
    ) -> None:
        """Trim the messages from and after the given message_id,
        and return the trimmed messages. current sequence to max sequence number is deleted"""
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)
        self._validate_uuid(message_id)

        async with self._cursor() as cur:
            await cur.execute(
                """SELECT sequence_number, role FROM v2_thread_message
                WHERE thread_id = :thread_id
                AND message_id = :message_id""",
                {"thread_id": thread_id, "message_id": message_id},
            )
            if not (message := await cur.fetchone()):
                raise ThreadNotFoundError(f"Message {message_id} not found")

            if message["role"] != "user":
                raise UserPermissionError(
                    f"User {user_id} does not have permission to edit message {message_id}",
                )
            await cur.execute(
                """DELETE FROM v2_thread_message
                WHERE thread_id = :thread_id
                AND sequence_number >= :sequence_number""",
                {"thread_id": thread_id, "sequence_number": message["sequence_number"]},
            )

    async def get_messages_by_parent_run_id(
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
                SELECT m.message_id, m.created_at, m.updated_at,
                       m.role, m.content, m.agent_metadata, m.server_metadata,
                       m.parent_run_id
                FROM   v2_thread_message AS m
                JOIN   v2_thread         AS t ON t.thread_id = m.thread_id
                WHERE  m.parent_run_id = :parent_run_id
                  AND  v2_check_user_access(t.user_id, :user_id)
                ORDER  BY m.sequence_number, m.created_at, m.message_id;
                """,
                {"parent_run_id": parent_run_id, "user_id": user_id},
            )
            rows = await cur.fetchall()

        if not rows:
            return []

        messages = []
        for row in rows:
            row_dict = dict(row)
            row_dict["content"] = json.loads(row_dict["content"]) if row_dict["content"] else []
            row_dict["agent_metadata"] = (
                json.loads(row_dict["agent_metadata"]) if row_dict["agent_metadata"] else {}
            )
            row_dict["server_metadata"] = (
                json.loads(row_dict["server_metadata"]) if row_dict["server_metadata"] else {}
            )
            # Set commited=True and completed=True for messages retrieved from database
            row_dict["commited"] = True  # Note: using "commited" to match the field name
            row_dict["complete"] = True
            messages.append(ThreadMessage.model_validate(row_dict))

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
                SELECT 1 FROM v2_thread AS t
                WHERE t.thread_id = :thread_id
                AND v2_check_user_access(
                    t.user_id, :user_id
                )
                LIMIT 1
                """,
                {"thread_id": thread_id, "user_id": user_id},
            )
            row = await cur.fetchone()
            return row is not None
