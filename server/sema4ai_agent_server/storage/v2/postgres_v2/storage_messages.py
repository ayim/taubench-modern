from psycopg import AsyncCursor
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from agent_server_types_v2.thread import ThreadMessage
from sema4ai_agent_server.storage.v2.errors_v2 import (
    RecordAlreadyExistsError,
    ThreadNotFoundError,
    UserAccessDeniedError,
)
from sema4ai_agent_server.storage.v2.postgres_v2.common import CommonMixin


class PostgresStorageMessagesMixin(CommonMixin):
    """Mixin for PostgreSQL message operations."""

    async def overwrite_thread_messages_v2(
        self,
        thread_id: str,
        messages: list[ThreadMessage],
        cursor: AsyncCursor|None=None,
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
            values = [{
                "message_id": msg["message_id"],
                "thread_id": thread_id,
                "sequence_number": i,
                "role": msg["role"],
                "content": Jsonb(msg["content"]),
                "agent_metadata": Jsonb(msg["agent_metadata"]),
                "server_metadata": Jsonb(msg["server_metadata"]),
                "created_at": msg["created_at"],
                "updated_at": msg["updated_at"],
                "parent_run_id": msg["parent_run_id"],
            } for i, msg in enumerate(messages)]

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

    async def add_message_to_thread_v2(
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

                # 3. Get the last message
                await cur.execute(
                    """SELECT sequence_number FROM v2.thread_message
                    WHERE thread_id = %(thread_id)s::uuid
                    ORDER BY sequence_number DESC LIMIT 1""",
                    {"thread_id": thread_id},
                )

                # 4. No messages found?
                if not (last_message := await cur.fetchone()):
                    sequence_number = 0
                else:
                    sequence_number = last_message["sequence_number"] + 1

                message_dict = message.model_dump()

                # 5. Insert the new message
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
            except UniqueViolation as e:
                if "duplicate key value violates unique constraint" in str(e):
                    raise RecordAlreadyExistsError(
                        f"Message {message_dict['message_id']} already exists",
                    ) from e
                raise e
            except Exception:
                raise

    async def get_thread_messages_v2(self, thread_id: str) -> list[ThreadMessage]:
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

            # 4. Return the messages
            return [ThreadMessage.model_validate(row) for row in messages]

    async def get_messages_by_parent_run_id_v2(
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
                """SELECT message_id, created_at, updated_at,
                    role, content, agent_metadata, server_metadata,
                    parent_run_id
                    FROM v2.thread_message
                    WHERE parent_run_id = %(parent_run_id)s::text
                    AND v2.check_user_access(
                        t.user_id, %(user_id)s::uuid
                    )
                    ORDER BY sequence_number, created_at, message_id""",
                {"parent_run_id": parent_run_id, "user_id": user_id},
            )

            # 3. No messages found?
            if not (messages := await cur.fetchall()):
                return []

            # 4. Return the messages
            return [ThreadMessage.model_validate(row) for row in messages]
