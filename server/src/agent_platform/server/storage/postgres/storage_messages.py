from psycopg import AsyncCursor
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from agent_platform.core.thread import ThreadMessage
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    ThreadNotFoundError,
    UserAccessDeniedError,
    UserPermissionError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageMessagesMixin(CursorMixin, CommonMixin):
    """Mixin for PostgreSQL message operations."""

    async def overwrite_thread_messages(
        self,
        thread_id: str,
        messages: list[ThreadMessage],
        cursor: AsyncCursor[DictRow] | None = None,
    ) -> None:
        """Overwrite the messages for the given thread."""
        # 1. Validate the uuid
        self._validate_uuid(thread_id)

        async with self._cursor(cursor) as cur:
            # 2. Delete existing messages
            await cur.execute(
                "DELETE FROM v2.thread_message WHERE thread_id = %(thread_id)s::uuid",
                {"thread_id": thread_id},
            )

            # 3. Perpare messages for batch insert
            values = [
                {
                    "message_id": msg.message_id,
                    "thread_id": thread_id,
                    "sequence_number": i,
                    "role": msg.role,
                    "content": Jsonb([c.model_dump() for c in msg.content]),
                    "agent_metadata": Jsonb(msg.agent_metadata),
                    "server_metadata": Jsonb(msg.server_metadata),
                    "created_at": msg.created_at,
                    "updated_at": msg.updated_at,
                    "parent_run_id": msg.parent_run_id,
                }
                for i, msg in enumerate(messages)
            ]

            # 4. No values to insert?
            if not values:
                return

            # 5. Batch insert new messages
            await cur.executemany(
                """INSERT INTO v2.thread_message (
                    message_id, thread_id, sequence_number, role, content,
                    agent_metadata, server_metadata, created_at, updated_at,
                    parent_run_id
                ) VALUES (
                    %(message_id)s::uuid, %(thread_id)s::uuid, %(sequence_number)s,
                    %(role)s, %(content)s, %(agent_metadata)s, %(server_metadata)s,
                    %(created_at)s, %(updated_at)s, %(parent_run_id)s
                )""",
                values,
            )

    async def add_message_to_thread(
        self,
        user_id: str,
        thread_id: str,
        message: ThreadMessage,
    ) -> None:
        """Add a message to the given thread."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            try:
                # 2. Check if the user has access
                await cur.execute(
                    """SELECT v2.check_user_access(
                        t.user_id, %(user_id)s::uuid
                    ) as has_access
                    FROM v2.thread t
                    WHERE t.thread_id = %(thread_id)s::uuid""",
                    {"thread_id": thread_id, "user_id": user_id},
                )

                if not (row := await cur.fetchone()):
                    raise ThreadNotFoundError(f"Thread {thread_id} not found")
                if not row["has_access"]:
                    raise UserAccessDeniedError(
                        f"User {user_id} does not have access to thread {thread_id}",
                    )

                message_dict = message.model_dump()

                # 3. Check if message already exists
                await cur.execute(
                    """SELECT sequence_number FROM v2.thread_message
                    WHERE message_id = %(message_id)s::uuid""",
                    {"message_id": message_dict["message_id"]},
                )
                existing_message = await cur.fetchone()

                if existing_message:
                    # 4. Message exists, update it (preserving sequence number)
                    await cur.execute(
                        """UPDATE v2.thread_message
                        SET role = %(role)s,
                            content = %(content)s,
                            agent_metadata = %(agent_metadata)s,
                            server_metadata = %(server_metadata)s,
                            updated_at = %(updated_at)s
                        WHERE message_id = %(message_id)s::uuid""",
                        {
                            "message_id": message_dict["message_id"],
                            "role": message_dict["role"],
                            "content": Jsonb(message_dict["content"]),
                            "agent_metadata": Jsonb(message_dict["agent_metadata"]),
                            "server_metadata": Jsonb(message_dict["server_metadata"]),
                            "updated_at": message_dict["updated_at"],
                        },
                    )
                else:
                    # 5. Message doesn't exist, get the next sequence number and insert
                    await cur.execute(
                        """SELECT sequence_number FROM v2.thread_message
                        WHERE thread_id = %(thread_id)s::uuid
                        ORDER BY sequence_number DESC LIMIT 1""",
                        {"thread_id": thread_id},
                    )

                    # 6. No messages found?
                    if not (last_message := await cur.fetchone()):
                        sequence_number = 0
                    else:
                        sequence_number = last_message["sequence_number"] + 1

                    # 7. Insert the new message
                    await cur.execute(
                        """INSERT INTO v2.thread_message (
                            message_id, thread_id, sequence_number, role, content,
                            agent_metadata, server_metadata, created_at, updated_at,
                            parent_run_id
                        ) VALUES (
                            %(message_id)s::uuid, %(thread_id)s::uuid,
                            %(sequence_number)s, %(role)s, %(content)s,
                            %(agent_metadata)s, %(server_metadata)s, %(created_at)s,
                            %(updated_at)s, %(parent_run_id)s
                        )""",
                        {
                            "message_id": message_dict["message_id"],
                            "thread_id": thread_id,
                            "sequence_number": sequence_number,
                            "role": message_dict["role"],
                            "content": Jsonb(message_dict["content"]),
                            "agent_metadata": Jsonb(message_dict["agent_metadata"]),
                            "server_metadata": Jsonb(message_dict["server_metadata"]),
                            "created_at": message_dict["created_at"],
                            "updated_at": message_dict["updated_at"],
                            "parent_run_id": message_dict["parent_run_id"],
                        },
                    )
            except ForeignKeyViolation as e:
                raise ThreadNotFoundError(
                    f"Thread with ID {thread_id} not found",
                ) from e
            except Exception:
                raise

    async def get_thread_messages(self, thread_id: str) -> list[ThreadMessage]:
        """Get the messages for the given thread,
        in ascending sequence/creation order."""
        # 1. Validate the uuids
        self._validate_uuid(thread_id)

        async with self._cursor() as cur:
            # 2. Get the messages
            await cur.execute(
                """SELECT message_id, created_at, updated_at,
                    role, content, agent_metadata, server_metadata,
                    parent_run_id
                    FROM v2.thread_message
                    WHERE thread_id = %(thread_id)s::uuid
                    ORDER BY sequence_number, created_at, message_id""",
                {"thread_id": thread_id},
            )

            # 3. No messages found?
            if not (messages := await cur.fetchall()):
                return []

            # 4. Return the messages with commited=True and completed=True
            # since they are already persisted in the database
            result_messages = []
            for row in messages:
                row_dict = dict(row)
                # Set commited=True and completed=True for messages retrieved from database
                row_dict["commited"] = True  # Note: using "commited" to match the field name
                row_dict["complete"] = True
                result_messages.append(ThreadMessage.model_validate(row_dict))
            return result_messages

    async def trim_messages_from_sequence(
        self,
        user_id: str,
        thread_id: str,
        message_id: str,
    ) -> None:
        """Trim the messages from and after the given message_id,
        and return the trimmed messages. current sequence to max sequence number is deleted"""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(thread_id)
        self._validate_uuid(message_id)

        async with self._cursor() as cur:
            # 2. Get the messages
            await cur.execute(
                """SELECT sequence_number, role FROM v2.thread_message
                WHERE thread_id = %(thread_id)s::uuid
                AND message_id = %(message_id)s::uuid""",
                {"thread_id": thread_id, "message_id": message_id},
            )

            if not (message := await cur.fetchone()):
                raise ThreadNotFoundError(f"Message {message_id} not found")

            if message["role"] != "user":
                raise UserPermissionError(
                    f"User {user_id} does not have permission to edit message {message_id}",
                )

            sequence_number = message["sequence_number"]

            # 3. Delete the messages
            await cur.execute(
                """DELETE FROM v2.thread_message
                WHERE thread_id = %(thread_id)s::uuid
                AND sequence_number >= %(sequence_number)s""",
                {"thread_id": thread_id, "sequence_number": sequence_number},
            )

    async def get_messages_by_parent_run_id(
        self,
        user_id: str,
        parent_run_id: str,
    ) -> list[ThreadMessage]:
        """Get messages for the given parent run ID,
        in ascending sequence/creation order."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)
        self._validate_uuid(parent_run_id)

        async with self._cursor() as cur:
            # 2. Get the messages
            await cur.execute(
                """SELECT
                    m.message_id, m.created_at, m.updated_at,
                    m.role, m.content, m.agent_metadata, m.server_metadata,
                    m.parent_run_id
                FROM v2.thread_message AS m
                JOIN v2.thread AS t ON t.thread_id = m.thread_id
                WHERE m.parent_run_id = %(parent_run_id)s::text
                  AND v2.check_user_access(t.user_id, %(user_id)s::uuid)
                ORDER BY m.sequence_number, m.created_at, m.message_id""",
                {"parent_run_id": parent_run_id, "user_id": user_id},
            )

            # 3. No messages found?
            if not (messages := await cur.fetchall()):
                return []

            # 4. Return the messages with commited=True and completed=True
            # since they are already persisted in the database
            result_messages = []
            for row in messages:
                row_dict = dict(row)
                # Set commited=True and completed=True for messages retrieved from database
                row_dict["commited"] = True  # Note: using "commited" to match the field name
                row_dict["complete"] = True
                result_messages.append(ThreadMessage.model_validate(row_dict))
            return result_messages
