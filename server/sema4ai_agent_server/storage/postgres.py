import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import asyncpg
import orjson
import structlog
from langchain_core.messages import AnyMessage
from pydantic import parse_obj_as

from sema4ai_agent_server.agent import AgentType, agent, get_agent_executor
from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.schema import Assistant, Thread, UploadedFile, User
from sema4ai_agent_server.storage import BaseStorage

logger = structlog.get_logger()


class PostgresStorage(BaseStorage):
    _pool: asyncpg.pool.Pool = None
    _is_setup: bool = False

    async def setup(self) -> None:
        if self._is_setup:
            return
        self._pool = await asyncpg.create_pool(
            database=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            init=self._init_connection,
        )
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        await self._pool.close()
        self._pool = None
        self._is_setup = False

    async def _init_connection(self, conn) -> None:
        await conn.set_type_codec(
            "json",
            encoder=lambda v: orjson.dumps(v).decode(),
            decoder=orjson.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "jsonb",
            encoder=lambda v: orjson.dumps(v).decode(),
            decoder=orjson.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "uuid", encoder=lambda v: str(v), decoder=lambda v: v, schema="pg_catalog"
        )

    def get_pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise Exception("Pool has not been created.")
        return self._pool

    async def list_all_assistants(self) -> List[Assistant]:
        async with self.get_pool().acquire() as conn:
            return await conn.fetch("SELECT * FROM assistant ")

    async def assistant_count(self) -> int:
        """Get assistant row count"""
        async with self.get_pool().acquire() as conn:
            result = await conn.fetchrow("SELECT COUNT(*) FROM assistant")
            count = result[0]
            return count

    async def thread_count(self) -> int:
        async with self.get_pool().acquire() as conn:
            result = await conn.fetchrow("SELECT COUNT(*) FROM thread")
            count = result[0]
            return count

    async def get_assistant_files(self, assistant_id: str) -> list[UploadedFile]:
        """Get a list of files associated with an assistant."""
        async with self.get_pool().acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM file_owners WHERE assistant_id = $1",
                assistant_id,
            )
            return [
                UploadedFile(
                    file_id=str(row["file_id"]),
                    file_path=row["file_path"],
                    file_ref=row["file_ref"],
                    file_hash=row["file_hash"],
                    embedded=row["embedded"],
                )
                for row in rows
            ]

    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        async with self.get_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM file_owners WHERE thread_id = $1
                """,
                thread_id,
            )
            return [
                UploadedFile(
                    file_id=str(row["file_id"]),
                    file_path=row["file_path"],
                    file_ref=row["file_ref"],
                    file_hash=row["file_hash"],
                    embedded=row["embedded"],
                )
                for row in rows
            ]

    async def get_file_by_id(self, file_id: str) -> Optional[UploadedFile]:
        """Get a file by id."""
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM file_owners
                WHERE file_id = $1
                """,
                file_id,
            )
            if not row:
                return None
            return UploadedFile(
                file_id=str(row["file_id"]),
                file_path=row["file_path"],
                file_ref=row["file_ref"],
                file_hash=row["file_hash"],
                embedded=row["embedded"],
            )

    async def get_file(
        self, owner: Union[Assistant, Thread], file_ref: str
    ) -> Optional[UploadedFile]:
        """Get a file by ref."""
        if isinstance(owner, Assistant):
            query = "assistant_id = $2"
            value = owner.assistant_id
        else:
            query = "thread_id = $2"
            value = owner.thread_id
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM file_owners
                WHERE file_ref = $1
                AND {query}
                """,
                file_ref,
                value,
            )
            if not row:
                return None
            return UploadedFile(
                file_id=str(row["file_id"]),
                file_path=row["file_path"],
                file_ref=row["file_ref"],
                file_hash=row["file_hash"],
                embedded=row["embedded"],
            )

    async def put_file_owner(
        self,
        file_id: str,
        file_path: Optional[str],
        file_ref: str,
        file_hash: str,
        embedded: bool,
        owner: Union[Assistant, Thread],
        file_path_expiration: Optional[datetime],
    ) -> UploadedFile:
        if isinstance(owner, Assistant):
            assistant_id = owner.assistant_id
            thread_id = None
        else:
            assistant_id = None
            thread_id = owner.thread_id
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO file_owners (file_id, file_path, file_ref, file_hash, embedded, assistant_id, thread_id, file_path_expiration)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT(file_id)
                DO UPDATE SET 
                    file_id = EXCLUDED.file_id,
                    file_path = EXCLUDED.file_path,
                    file_hash = EXCLUDED.file_hash,
                    embedded = EXCLUDED.embedded,
                    assistant_id = EXCLUDED.assistant_id,
                    thread_id = EXCLUDED.thread_id
                """,
                file_id,
                file_path,
                file_ref,
                file_hash,
                embedded,
                assistant_id,
                thread_id,
                file_path_expiration,
            )
            return UploadedFile(
                file_id=file_id,
                file_path=file_path,
                file_ref=file_ref,
                file_hash=file_hash,
                embedded=embedded,
            )

    async def delete_file(self, file_id: str) -> None:
        async with self.get_pool().acquire() as conn:
            await conn.execute("DELETE FROM file_owners WHERE file_id = $1", file_id)

    async def _run_migrations(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_path = Path(current_dir).parent / "migrations" / "postgres"

        async with self.get_pool().acquire() as conn:
            # Check if schema_migrations table exists and create it if it doesn't
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'schema_migrations'
                );
                """
            )
            if not table_exists:
                await conn.execute(
                    """
                    CREATE TABLE schema_migrations (
                        version BIGINT PRIMARY KEY, dirty BOOLEAN NOT NULL
                    );
                    """
                )
                await conn.execute(
                    "INSERT INTO schema_migrations (version, dirty) VALUES (0, FALSE);"
                )

            dirty_version = await conn.fetchval(
                "SELECT version FROM schema_migrations WHERE dirty = TRUE;"
            )
            if dirty_version:
                raise Exception(
                    f"Migration {dirty_version} is dirty. "
                    "No migrations will be applied. Please fix it manually."
                )

            current_version = await conn.fetchval(
                "SELECT version FROM schema_migrations;"
            )
            migration_files = sorted(
                (f for f in os.listdir(migrations_path) if f.endswith(".up.sql")),
                key=lambda x: int(x.split("_")[0]),
            )

            logger.info(f"Migrations found: {migration_files}")
            logger.info(f"Current migration version: {current_version}")

            for migration in migration_files:
                version = int(migration.split("_")[0])
                if version > current_version:
                    logger.info(f"Applying migration {migration}")

                    # Set dirty flag
                    await conn.execute(
                        "UPDATE schema_migrations SET version = $1, dirty = TRUE",
                        version,
                    )
                    # Try to apply the migration
                    with open(os.path.join(migrations_path, migration), "r") as f:
                        await conn.execute(f.read())
                    # Unset dirty flag
                    await conn.execute("UPDATE schema_migrations SET dirty = FALSE")

                    current_version = version

    async def list_assistants(self, user_id: str) -> List[Assistant]:
        """List all assistants for the current user."""
        async with self.get_pool().acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM assistant WHERE user_id = $1", user_id
            )

    async def get_assistant(
        self, user_id: str, assistant_id: str
    ) -> Optional[Assistant]:
        """Get an assistant by ID."""
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM assistant WHERE assistant_id = $1 AND (user_id = $2 OR public IS true)",
                assistant_id,
                user_id,
            )
            if not row:
                return None
            assistant_data = dict(row)  # Convert sqlite3.Row to dict
            assistant_data["config"] = (
                assistant_data["config"]
                if "config" in assistant_data and assistant_data["config"]
                else {}
            )
            assistant_data["metadata"] = (
                assistant_data["metadata"]
                if assistant_data["metadata"] is not None
                else None
            )
            return Assistant(**assistant_data)

    async def list_public_assistants(
        self, assistant_ids: Sequence[str]
    ) -> List[Assistant]:
        """List all the public assistants."""
        assistant_ids_tuple = tuple(
            assistant_ids
        )  # SQL requires a tuple for the IN operator.
        placeholders = ", ".join("?" for _ in assistant_ids)
        conn = self.get_pool().acquire()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM assistant WHERE assistant_id IN ({placeholders}) AND public = 1",
            assistant_ids_tuple,
        )
        rows = cursor.fetchall()
        return [Assistant(**dict(row)) for row in rows]

    async def put_assistant(
        self,
        user_id: str,
        assistant_id: str,
        *,
        name: str,
        config: dict,
        public: bool = False,
        metadata: Optional[dict],
    ) -> Assistant:
        """Modify an assistant.

        Args:
            user_id: The user ID.
            assistant_id: The assistant ID.
            name: The assistant name.
            config: The assistant config.
            public: Whether the assistant is public.
            metadata: Additional metadata.

        Returns:
            return the assistant model if no exception is raised.
        """
        updated_at = datetime.now(timezone.utc)
        conn = self.get_pool().acquire()
        async with self.get_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    (
                        "INSERT INTO assistant (assistant_id, user_id, name, config, updated_at, public, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7) "
                        "ON CONFLICT (assistant_id) DO UPDATE SET "
                        "user_id = EXCLUDED.user_id, "
                        "name = EXCLUDED.name, "
                        "config = EXCLUDED.config, "
                        "updated_at = EXCLUDED.updated_at, "
                        "public = EXCLUDED.public,"
                        "metadata = EXCLUDED.metadata;"
                    ),
                    assistant_id,
                    user_id,
                    name,
                    config,
                    updated_at,
                    public,
                    metadata,
                )
        return {
            "assistant_id": assistant_id,
            "user_id": user_id,
            "name": name,
            "config": config,
            "updated_at": updated_at,
            "public": public,
            "metadata": metadata,
        }

    async def delete_assistant(self, user_id: str, assistant_id: str) -> None:
        """Delete an assistant by ID."""
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "DELETE FROM assistant WHERE assistant_id = $1 AND user_id = $2",
                assistant_id,
                user_id,
            )

    async def list_threads(self, user_id: str) -> List[Thread]:
        """List all threads for the current user."""
        async with self.get_pool().acquire() as conn:
            threads = await conn.fetch(
                "SELECT * FROM thread WHERE user_id = $1", user_id
            )
            return parse_obj_as(List[Thread], threads)

    async def get_thread(self, user_id: str, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        async with self.get_pool().acquire() as conn:
            thread = await conn.fetchrow(
                "SELECT * FROM thread WHERE thread_id = $1 AND user_id = $2",
                thread_id,
                user_id,
            )
            return parse_obj_as(Optional[Thread], thread)

    async def get_thread_state(self, user_id: str, thread_id: str):
        """Get state for a thread."""
        app = get_agent_executor([], AgentType.GPT_35_TURBO, "", "", False, 0, None)
        state = app.get_state({"configurable": {"thread_id": thread_id}})
        return {
            "values": state.values,
            "next": state.next,
        }

    async def update_thread_state(
        self,
        user_id: str,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        thread = await self.get_thread(user_id, thread_id)
        assistant_id = thread.assistant_id
        assistant = await self.get_assistant(user_id, assistant_id)
        config = assistant["config"]["configurable"] if assistant else {}
        retval = agent.update_state(
            {
                "configurable": {
                    **config,
                    "thread_id": thread_id,
                    "assistant_id": assistant_id,
                }
            },
            values,
            as_node=as_node,
        )
        return retval

    async def get_thread_history(self, user_id: str, thread_id: str):
        """Get the history of a thread."""
        app = await get_agent_executor([], AgentType.GPT_35_TURBO, "", "", False, None)

        history = []
        for c in app.get_state_history({"configurable": {"thread_id": thread_id}}):
            history.append(
                {
                    "values": c.values,
                    "next": c.next,
                    "config": c.config,
                    "parent": c.parent_config,
                }
            )

        return history

    async def put_thread(
        self,
        user_id: str,
        thread_id: str,
        *,
        assistant_id: str,
        name: str,
        metadata: Optional[dict],
    ) -> Thread:
        """Modify a thread."""
        updated_at = datetime.now(timezone.utc)
        assistant = await self.get_assistant(user_id, assistant_id)
        metadata = (
            {"assistant_type": assistant["config"]["configurable"]["type"]}
            if assistant
            else None
        )
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                (
                    "INSERT INTO thread (thread_id, user_id, assistant_id, name, updated_at, metadata) VALUES ($1, $2, $3, $4, $5, $6) "
                    "ON CONFLICT (thread_id) DO UPDATE SET "
                    "user_id = EXCLUDED.user_id,"
                    "assistant_id = EXCLUDED.assistant_id, "
                    "name = EXCLUDED.name, "
                    "updated_at = EXCLUDED.updated_at, "
                    "metadata = EXCLUDED.metadata;"
                ),
                thread_id,
                user_id,
                assistant_id,
                name,
                updated_at,
                metadata,
            )
            return Thread(
                thread_id=thread_id,
                user_id=user_id,
                assistant_id=assistant_id,
                name=name,
                updated_at=updated_at,
                metadata=metadata,
            )

    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID."""
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "DELETE FROM thread WHERE thread_id = $1 AND user_id = $2",
                thread_id,
                user_id,
            )

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        async with self.get_pool().acquire() as conn:
            if user := await conn.fetchrow('SELECT * FROM "user" WHERE sub = $1', sub):
                return parse_obj_as(User, user), False
            user = await conn.fetchrow(
                'INSERT INTO "user" (sub) VALUES ($1) RETURNING *', sub
            )
            return parse_obj_as(User, user), True
